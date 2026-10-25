#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>

/*
 * PostgreSQL JSONB query-planning case study.
 *
 * The program models structured documents, typed path lookup, containment,
 * selected-field indexing, and safe updates. It uses only C++17.
 * A production JSON parser should be used when accepting external JSON text.
 */

class Json {
public:
    using Array = std::vector<Json>;
    using Object = std::map<std::string, Json>;
    using Value = std::variant<std::nullptr_t, bool, double, std::string, Array, Object>;

private:
    Value value_;

public:
    Json() : value_(nullptr) {}
    Json(std::nullptr_t) : value_(nullptr) {}
    Json(bool value) : value_(value) {}
    Json(double value) : value_(value) {
        if (!std::isfinite(value)) {
            throw std::invalid_argument("JSON numbers must be finite");
        }
    }
    Json(int value) : Json(static_cast<double>(value)) {}
    Json(std::string value) : value_(std::move(value)) {}
    Json(const char* value) : value_(std::string(value)) {}
    Json(Array value) : value_(std::move(value)) {}
    Json(Object value) : value_(std::move(value)) {}

    const Value& value() const { return value_; }

    const Object* object() const { return std::get_if<Object>(&value_); }
    const Array* array() const { return std::get_if<Array>(&value_); }

    std::optional<Json> get(const std::string& key) const {
        const auto* obj = object();
        if (!obj) return std::nullopt;
        const auto it = obj->find(key);
        if (it == obj->end()) return std::nullopt;
        return it->second;
    }

    std::string canonical() const {
        if (std::holds_alternative<std::nullptr_t>(value_)) return "null";
        if (const auto* b = std::get_if<bool>(&value_)) return *b ? "true" : "false";
        if (const auto* n = std::get_if<double>(&value_)) {
            std::ostringstream out;
            out << std::setprecision(15) << *n;
            return out.str();
        }
        if (const auto* s = std::get_if<std::string>(&value_)) {
            std::ostringstream out;
            out << '"';
            for (char c : *s) {
                if (c == '"' || c == '\\') out << '\\';
                if (c == '\n') out << "\\n";
                else out << c;
            }
            out << '"';
            return out.str();
        }
        if (const auto* a = array()) {
            std::string result = "[";
            for (std::size_t i = 0; i < a->size(); ++i) {
                if (i) result += ",";
                result += (*a)[i].canonical();
            }
            return result + "]";
        }
        const auto& obj = std::get<Object>(value_);
        std::string result = "{";
        bool first = true;
        for (const auto& [key, item] : obj) {
            if (!first) result += ",";
            first = false;
            result += Json(key).canonical() + ":" + item.canonical();
        }
        return result + "}";
    }

    bool contains(const Json& expected) const {
        if (const auto* expectedObject = expected.object()) {
            const auto* actualObject = object();
            if (!actualObject) return false;

            for (const auto& [key, value] : *expectedObject) {
                const auto it = actualObject->find(key);
                if (it == actualObject->end() || !it->second.contains(value)) {
                    return false;
                }
            }
            return true;
        }

        if (const auto* expectedArray = expected.array()) {
            const auto* actualArray = array();
            if (!actualArray) return false;

            for (const Json& expectedItem : *expectedArray) {
                const bool found = std::any_of(
                    actualArray->begin(), actualArray->end(),
                    [&](const Json& actualItem) {
                        return actualItem.contains(expectedItem);
                    }
                );
                if (!found) return false;
            }
            return true;
        }

        // JSONB distinguishes booleans from numbers and strings from both.
        return canonical() == expected.canonical() &&
               value_.index() == expected.value_.index();
    }
};

struct Product {
    std::int64_t id;
    std::string name;
    std::string category;
    std::int64_t priceCents;
    Json attributes;
};

class DocumentStore {
private:
    std::map<std::int64_t, Product> products_;
    std::map<std::string, std::set<std::int64_t>> categoryIndex_;
    std::map<std::string, std::set<std::int64_t>> attributeIndex_;
    std::int64_t nextId_ = 1;

    static std::string attributeKey(const std::string& key, const Json& value) {
        return key + "\x1f" + value.canonical();
    }

    void index(const Product& product) {
        categoryIndex_[product.category].insert(product.id);

        const auto* attributes = product.attributes.object();
        if (!attributes) return;

        for (const auto& [key, value] : *attributes) {
            if (value.value().index() <= 3) {
                attributeIndex_[attributeKey(key, value)].insert(product.id);
            }
        }
    }

    void unindex(const Product& product) {
        auto category = categoryIndex_.find(product.category);
        if (category != categoryIndex_.end()) {
            category->second.erase(product.id);
            if (category->second.empty()) categoryIndex_.erase(category);
        }

        const auto* attributes = product.attributes.object();
        if (!attributes) return;

        for (const auto& [key, value] : *attributes) {
            if (value.value().index() <= 3) {
                auto it = attributeIndex_.find(attributeKey(key, value));
                if (it != attributeIndex_.end()) {
                    it->second.erase(product.id);
                    if (it->second.empty()) attributeIndex_.erase(it);
                }
            }
        }
    }

public:
    Product add(std::string name, std::string category,
                std::int64_t priceCents, Json attributes) {
        if (name.empty() || name.size() > 120) {
            throw std::invalid_argument("Invalid product name");
        }
        if (category.empty() || category.size() > 50) {
            throw std::invalid_argument("Invalid category");
        }
        if (priceCents < 0) {
            throw std::invalid_argument("Price cannot be negative");
        }
        if (!attributes.object()) {
            throw std::invalid_argument("Attributes must be a JSON object");
        }

        Product product{
            nextId_++, std::move(name), std::move(category),
            priceCents, std::move(attributes)
        };

        products_.emplace(product.id, product);
        index(product);
        return product;
    }

    std::vector<Product> byCategory(const std::string& category) const {
        std::vector<Product> result;
        const auto it = categoryIndex_.find(category);
        if (it == categoryIndex_.end()) return result;

        for (const auto id : it->second) result.push_back(products_.at(id));
        return result;
    }

    std::vector<Product> byAttribute(const std::string& key,
                                     const Json& expected) const {
        std::vector<Product> result;
        const auto it = attributeIndex_.find(attributeKey(key, expected));
        if (it == attributeIndex_.end()) return result;

        for (const auto id : it->second) result.push_back(products_.at(id));
        return result;
    }

    std::vector<Product> containing(const Json& required) const {
        std::vector<Product> result;
        for (const auto& [id, product] : products_) {
            if (product.attributes.contains(required)) result.push_back(product);
        }
        return result;
    }

    std::optional<Json> path(std::int64_t id,
                             const std::vector<std::string>& segments) const {
        const auto product = products_.find(id);
        if (product == products_.end()) return std::nullopt;

        Json current = product->second.attributes;
        for (const auto& segment : segments) {
            auto next = current.get(segment);
            if (!next) return std::nullopt;
            current = *next;
        }
        return current;
    }

    void updateAttributes(std::int64_t id, const Json& patch) {
        auto it = products_.find(id);
        if (it == products_.end()) {
            throw std::invalid_argument("Product does not exist");
        }
        if (!patch.object()) {
            throw std::invalid_argument("Patch must be a JSON object");
        }

        Json::Object merged = *it->second.attributes.object();
        for (const auto& [key, value] : *patch.object()) {
            merged[key] = value;
        }

        Product replacement = it->second;
        replacement.attributes = Json(std::move(merged));

        // Indexes and stored data change together after validation succeeds.
        unindex(it->second);
        it->second = replacement;
        index(it->second);
    }
};

int main() {
    try {
        DocumentStore store;

        Product laptop = store.add(
            "Engineering Laptop", "electronics", 129999,
            Json::Object{
                {"brand", "Northstar"},
                {"wireless", true},
                {"specs", Json::Object{
                    {"ram_gb", 32},
                    {"storage_gb", 1024}
                }},
                {"ports", Json::Array{"USB-C", "HDMI"}}
            }
        );

        store.add(
            "Operations Monitor", "electronics", 34950,
            Json::Object{
                {"brand", "Northstar"},
                {"wireless", false},
                {"specs", Json::Object{{"ram_gb", 0}}},
                {"ports", Json::Array{"HDMI", "DisplayPort"}}
            }
        );

        std::cout << "Electronics count: "
                  << store.byCategory("electronics").size() << '\n';

        std::cout << "Wireless product count: "
                  << store.byAttribute("wireless", Json(true)).size() << '\n';

        Json required(Json::Object{
            {"specs", Json::Object{{"ram_gb", 32}}}
        });

        std::cout << "32 GB RAM matches: "
                  << store.containing(required).size() << '\n';

        auto ram = store.path(laptop.id, {"specs", "ram_gb"});
        if (ram) {
            std::cout << "Laptop RAM: " << ram->canonical() << '\n';
        }

        store.updateAttributes(
            2, Json::Object{{"wireless", true}, {"warranty_years", 3}}
        );

        std::cout << "Wireless after update: "
                  << store.byAttribute("wireless", Json(true)).size() << '\n';

        try {
            store.add("Invalid", "electronics", -1, Json::Object{});
        } catch (const std::invalid_argument& error) {
            std::cout << "Rejected invalid product: " << error.what() << '\n';
        }

        if (store.containing(required).size() != 1) {
            throw std::runtime_error("Containment assertion failed");
        }

        std::cout << "All assertions passed.\n";
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
