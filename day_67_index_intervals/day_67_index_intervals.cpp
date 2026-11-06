#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <queue>
#include <random>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using namespace std;

enum class PageType {
    LEAF,
    INTERNAL
};

struct IndexPage {
    int page_id;
    PageType type;
    vector<int> keys;
    vector<string> values;
    vector<shared_ptr<IndexPage>> children;
    shared_ptr<IndexPage> next_leaf;
    weak_ptr<IndexPage> parent;

    IndexPage(int id, PageType page_type)
        : page_id(id), type(page_type) {}

    bool is_leaf() const {
        return type == PageType::LEAF;
    }
};

class BPlusTree {
private:
    int order_;
    int max_keys_;
    int min_leaf_keys_;
    int min_internal_children_;
    int next_page_id_ = 1;
    size_t size_ = 0;

    shared_ptr<IndexPage> root_;

    size_t page_reads_ = 0;
    size_t page_writes_ = 0;
    size_t splits_ = 0;

    shared_ptr<IndexPage> create_page(PageType type) {
        return make_shared<IndexPage>(next_page_id_++, type);
    }

    void read_page(const shared_ptr<IndexPage>& page) {
        ++page_reads_;
    }

    void write_page(const shared_ptr<IndexPage>& page) {
        ++page_writes_;
    }

    int minimum(const shared_ptr<IndexPage>& page) const {
        auto current = page;

        while (!current->is_leaf()) {
            current = current->children.front();
        }

        return current->keys.front();
    }

    void refresh(const shared_ptr<IndexPage>& page) {
        if (page->is_leaf()) {
            return;
        }

        page->keys.clear();

        for (size_t i = 1; i < page->children.size(); ++i) {
            page->keys.push_back(minimum(page->children[i]));
        }
    }

    shared_ptr<IndexPage> find_leaf(int key) {
        auto page = root_;

        while (!page->is_leaf()) {
            read_page(page);

            auto it = upper_bound(
                page->keys.begin(),
                page->keys.end(),
                key
            );

            size_t index = distance(page->keys.begin(), it);
            page = page->children[index];
        }

        read_page(page);
        return page;
    }

    void insert_parent(
        const shared_ptr<IndexPage>& left,
        const shared_ptr<IndexPage>& right
    ) {
        auto parent = left->parent.lock();

        if (!parent) {
            parent = create_page(PageType::INTERNAL);
            parent->children = {left, right};

            left->parent = parent;
            right->parent = parent;

            refresh(parent);
            root_ = parent;
            write_page(parent);
            return;
        }

        auto it = find(
            parent->children.begin(),
            parent->children.end(),
            left
        );

        if (it == parent->children.end()) {
            throw logic_error("Parent does not reference child");
        }

        size_t index = distance(parent->children.begin(), it);

        parent->children.insert(
            parent->children.begin() + index + 1,
            right
        );

        right->parent = parent;
        refresh(parent);
        write_page(parent);

        if (static_cast<int>(parent->children.size()) > order_) {
            split_internal(parent);
        }
    }

    void split_leaf(const shared_ptr<IndexPage>& leaf) {
        size_t middle = leaf->keys.size() / 2;
        auto right = create_page(PageType::LEAF);

        right->keys.assign(
            leaf->keys.begin() + middle,
            leaf->keys.end()
        );

        right->values.assign(
            leaf->values.begin() + middle,
            leaf->values.end()
        );

        leaf->keys.resize(middle);
        leaf->values.resize(middle);

        right->next_leaf = leaf->next_leaf;
        leaf->next_leaf = right;

        ++splits_;
        write_page(leaf);
        write_page(right);

        insert_parent(leaf, right);
    }

    void split_internal(const shared_ptr<IndexPage>& page) {
        size_t middle = page->children.size() / 2;
        auto right = create_page(PageType::INTERNAL);

        right->children.assign(
            page->children.begin() + middle,
            page->children.end()
        );

        page->children.resize(middle);

        for (const auto& child : right->children) {
            child->parent = right;
        }

        refresh(page);
        refresh(right);

        ++splits_;
        write_page(page);
        write_page(right);

        insert_parent(page, right);
    }

    void repair_ancestors(shared_ptr<IndexPage> page) {
        while (page) {
            refresh(page);
            write_page(page);
            page = page->parent.lock();
        }
    }

    void rebalance_leaf(const shared_ptr<IndexPage>& leaf) {
        auto parent = leaf->parent.lock();

        auto it = find(
            parent->children.begin(),
            parent->children.end(),
            leaf
        );

        size_t index = distance(parent->children.begin(), it);

        shared_ptr<IndexPage> left =
            index > 0 ? parent->children[index - 1] : nullptr;

        shared_ptr<IndexPage> right =
            index + 1 < parent->children.size()
                ? parent->children[index + 1]
                : nullptr;

        if (left &&
            static_cast<int>(left->keys.size()) > min_leaf_keys_) {
            leaf->keys.insert(
                leaf->keys.begin(),
                left->keys.back()
            );

            leaf->values.insert(
                leaf->values.begin(),
                left->values.back()
            );

            left->keys.pop_back();
            left->values.pop_back();

            write_page(left);
            write_page(leaf);
        } else if (right &&
                   static_cast<int>(right->keys.size()) > min_leaf_keys_) {
            leaf->keys.push_back(right->keys.front());
            leaf->values.push_back(right->values.front());

            right->keys.erase(right->keys.begin());
            right->values.erase(right->values.begin());

            write_page(right);
            write_page(leaf);
        } else if (left) {
            left->keys.insert(
                left->keys.end(),
                leaf->keys.begin(),
                leaf->keys.end()
            );

            left->values.insert(
                left->values.end(),
                leaf->values.begin(),
                leaf->values.end()
            );

            left->next_leaf = leaf->next_leaf;

            parent->children.erase(
                parent->children.begin() + index
            );

            write_page(left);
            repair_internal(parent);
        } else if (right) {
            leaf->keys.insert(
                leaf->keys.end(),
                right->keys.begin(),
                right->keys.end()
            );

            leaf->values.insert(
                leaf->values.end(),
                right->values.begin(),
                right->values.end()
            );

            leaf->next_leaf = right->next_leaf;

            parent->children.erase(
                parent->children.begin() + index + 1
            );

            write_page(leaf);
            repair_internal(parent);
        }
    }

    void repair_internal(const shared_ptr<IndexPage>& page) {
        if (page == root_) {
            if (page->children.size() == 1) {
                root_ = page->children.front();
                root_->parent.reset();
            } else {
                refresh(page);
            }
            return;
        }

        refresh(page);

        if (static_cast<int>(page->children.size()) >=
            min_internal_children_) {
            repair_ancestors(page->parent.lock());
            return;
        }

        auto parent = page->parent.lock();

        auto it = find(
            parent->children.begin(),
            parent->children.end(),
            page
        );

        size_t index = distance(parent->children.begin(), it);

        shared_ptr<IndexPage> left =
            index > 0 ? parent->children[index - 1] : nullptr;

        shared_ptr<IndexPage> right =
            index + 1 < parent->children.size()
                ? parent->children[index + 1]
                : nullptr;

        if (left &&
            static_cast<int>(left->children.size()) >
                min_internal_children_) {
            auto child = left->children.back();
            left->children.pop_back();

            page->children.insert(
                page->children.begin(),
                child
            );

            child->parent = page;
            refresh(left);
            refresh(page);
        } else if (right &&
                   static_cast<int>(right->children.size()) >
                       min_internal_children_) {
            auto child = right->children.front();
            right->children.erase(right->children.begin());

            page->children.push_back(child);
            child->parent = page;

            refresh(right);
            refresh(page);
        } else if (left) {
            left->children.insert(
                left->children.end(),
                page->children.begin(),
                page->children.end()
            );

            for (const auto& child : page->children) {
                child->parent = left;
            }

            parent->children.erase(
                parent->children.begin() + index
            );

            refresh(left);
        } else if (right) {
            page->children.insert(
                page->children.end(),
                right->children.begin(),
                right->children.end()
            );

            for (const auto& child : right->children) {
                child->parent = page;
            }

            parent->children.erase(
                parent->children.begin() + index + 1
            );
        }

        refresh(parent);
        write_page(parent);
        repair_internal(parent);
    }

    pair<int, int> inspect(
        const shared_ptr<IndexPage>& page,
        bool is_root,
        unordered_set<int>& visited,
        vector<shared_ptr<IndexPage>>& leaves
    ) const {
        if (!visited.insert(page->page_id).second) {
            throw logic_error("Page cycle detected");
        }

        if (page->is_leaf()) {
            if (page->keys.size() != page->values.size()) {
                throw logic_error("Leaf value count mismatch");
            }

            if (!is_sorted(page->keys.begin(), page->keys.end())) {
                throw logic_error("Unsorted leaf");
            }

            if (adjacent_find(
                    page->keys.begin(),
                    page->keys.end()
                ) != page->keys.end()) {
                throw logic_error("Duplicate leaf key");
            }

            if (static_cast<int>(page->keys.size()) > max_keys_) {
                throw logic_error("Leaf overflow");
            }

            if (!is_root &&
                static_cast<int>(page->keys.size()) < min_leaf_keys_) {
                throw logic_error("Leaf underflow");
            }

            leaves.push_back(page);

            if (page->keys.empty()) {
                return {INT32_MAX, INT32_MIN};
            }

            return {page->keys.front(), page->keys.back()};
        }

        if (page->children.size() != page->keys.size() + 1) {
            throw logic_error("Invalid internal pointer count");
        }

        if (page->children.size() > static_cast<size_t>(order_)) {
            throw logic_error("Internal overflow");
        }

        if (is_root && page->children.size() < 2) {
            throw logic_error("Invalid internal root");
        }

        if (!is_root &&
            static_cast<int>(page->children.size()) <
                min_internal_children_) {
            throw logic_error("Internal underflow");
        }

        vector<pair<int, int>> ranges;

        for (const auto& child : page->children) {
            if (child->parent.lock() != page) {
                throw logic_error("Invalid parent pointer");
            }

            ranges.push_back(
                inspect(child, false, visited, leaves)
            );
        }

        vector<int> expected;

        for (size_t i = 1; i < ranges.size(); ++i) {
            expected.push_back(ranges[i].first);
        }

        if (expected != page->keys) {
            throw logic_error("Separator key mismatch");
        }

        for (size_t i = 1; i < ranges.size(); ++i) {
            if (ranges[i - 1].second >= ranges[i].first) {
                throw logic_error("Overlapping child ranges");
            }
        }

        return {ranges.front().first, ranges.back().second};
    }

public:
    explicit BPlusTree(int order = 5)
        : order_(order),
          max_keys_(order - 1),
          min_leaf_keys_(order / 2),
          min_internal_children_((order + 1) / 2) {
        if (order < 3) {
            throw invalid_argument("Order must be at least 3");
        }

        root_ = create_page(PageType::LEAF);
    }

    void insert(int key, const string& value) {
        auto leaf = find_leaf(key);

        auto it = lower_bound(
            leaf->keys.begin(),
            leaf->keys.end(),
            key
        );

        if (it != leaf->keys.end() && *it == key) {
            throw invalid_argument("Duplicate key");
        }

        size_t index = distance(leaf->keys.begin(), it);

        leaf->keys.insert(it, key);
        leaf->values.insert(
            leaf->values.begin() + index,
            value
        );

        ++size_;
        write_page(leaf);

        if (static_cast<int>(leaf->keys.size()) > max_keys_) {
            split_leaf(leaf);
        }

        repair_ancestors(leaf->parent.lock());
    }

    string search(int key) {
        auto leaf = find_leaf(key);

        auto it = lower_bound(
            leaf->keys.begin(),
            leaf->keys.end(),
            key
        );

        if (it == leaf->keys.end() || *it != key) {
            throw out_of_range("Key not found");
        }

        return leaf->values[
            distance(leaf->keys.begin(), it)
        ];
    }

    vector<pair<int, string>> range_scan(int start, int end) {
        vector<pair<int, string>> results;

        if (start > end) {
            return results;
        }

        auto leaf = find_leaf(start);

        while (leaf) {
            read_page(leaf);

            for (size_t i = 0; i < leaf->keys.size(); ++i) {
                if (leaf->keys[i] > end) {
                    return results;
                }

                if (leaf->keys[i] >= start) {
                    results.push_back({
                        leaf->keys[i],
                        leaf->values[i]
                    });
                }
            }

            leaf = leaf->next_leaf;
        }

        return results;
    }

    vector<int> traverse() {
        vector<int> result;
        auto page = root_;

        while (!page->is_leaf()) {
            page = page->children.front();
        }

        while (page) {
            read_page(page);

            result.insert(
                result.end(),
                page->keys.begin(),
                page->keys.end()
            );

            page = page->next_leaf;
        }

        return result;
    }

    vector<map<string, string>> page_report() const {
        vector<map<string, string>> output;
        queue<shared_ptr<IndexPage>> pending;
        pending.push(root_);

        while (!pending.empty()) {
            auto page = pending.front();
            pending.pop();

            string keys;

            for (int key : page->keys) {
                if (!keys.empty()) keys += ",";
                keys += to_string(key);
            }

            string children;

            for (const auto& child : page->children) {
                if (!children.empty()) children += ",";
                children += to_string(child->page_id);
                pending.push(child);
            }

            output.push_back({
                {"page_id", to_string(page->page_id)},
                {"type", page->is_leaf() ? "LEAF" : "INTERNAL"},
                {"keys", keys},
                {"children", children},
                {"next_leaf", page->next_leaf
                    ? to_string(page->next_leaf->page_id)
                    : "NULL"}
            });
        }

        return output;
    }

    void erase(int key) {
        auto leaf = find_leaf(key);

        auto it = lower_bound(
            leaf->keys.begin(),
            leaf->keys.end(),
            key
        );

        if (it == leaf->keys.end() || *it != key) {
            throw out_of_range("Key not found");
        }

        size_t index = distance(leaf->keys.begin(), it);

        leaf->keys.erase(it);
        leaf->values.erase(leaf->values.begin() + index);

        --size_;
        write_page(leaf);

        if (leaf == root_) {
            return;
        }

        if (static_cast<int>(leaf->keys.size()) < min_leaf_keys_) {
            rebalance_leaf(leaf);
        }

        repair_ancestors(leaf->parent.lock());
    }

    bool validate() const {
        unordered_set<int> visited;
        vector<shared_ptr<IndexPage>> leaves;

        inspect(root_, true, visited, leaves);

        size_t total = 0;

        for (size_t i = 0; i < leaves.size(); ++i) {
            auto expected =
                i + 1 < leaves.size() ? leaves[i + 1] : nullptr;

            if (leaves[i]->next_leaf != expected) {
                throw logic_error("Invalid leaf chain");
            }

            total += leaves[i]->keys.size();
        }

        if (total != size_) {
            throw logic_error("Incorrect record count");
        }

        return true;
    }

    void statistics() const {
        auto report = page_report();

        size_t leaf_pages = 0;
        size_t internal_pages = 0;

        for (const auto& page : report) {
            if (page.at("type") == "LEAF") {
                ++leaf_pages;
            } else {
                ++internal_pages;
            }
        }

        int height = 0;
        auto page = root_;

        while (page) {
            ++height;
            page = page->is_leaf()
                ? nullptr
                : page->children.front();
        }

        cout << "Records: " << size_ << '\n';
        cout << "Height: " << height << '\n';
        cout << "Total pages: " << report.size() << '\n';
        cout << "Leaf pages: " << leaf_pages << '\n';
        cout << "Internal pages: " << internal_pages << '\n';
        cout << "Splits: " << splits_ << '\n';
        cout << "Page reads: " << page_reads_ << '\n';
        cout << "Page writes: " << page_writes_ << '\n';
    }
};

class BufferPool {
private:
    size_t capacity_;
    list<int> recency_;
    unordered_map<int, list<int>::iterator> entries_;

    size_t hits_ = 0;
    size_t misses_ = 0;
    size_t evictions_ = 0;

public:
    explicit BufferPool(size_t capacity)
        : capacity_(capacity) {
        if (capacity == 0) {
            throw invalid_argument("Capacity must be positive");
        }
    }

    void access(int page_id) {
        auto it = entries_.find(page_id);

        if (it != entries_.end()) {
            ++hits_;
            recency_.erase(it->second);
            recency_.push_back(page_id);
            it->second = prev(recency_.end());
            return;
        }

        ++misses_;

        if (entries_.size() == capacity_) {
            int victim = recency_.front();
            recency_.pop_front();
            entries_.erase(victim);
            ++evictions_;
        }

        recency_.push_back(page_id);
        entries_[page_id] = prev(recency_.end());
    }

    void report() const {
        size_t total = hits_ + misses_;

        cout << "Buffer hits: " << hits_ << '\n';
        cout << "Buffer misses: " << misses_ << '\n';
        cout << "Evictions: " << evictions_ << '\n';

        cout << "Hit ratio: "
             << (total ? static_cast<double>(hits_) / total : 0.0)
             << '\n';
    }
};

int main() {
    try {
        cout << "B+ TREE INDEX INTERNALS\n";
        cout << string(60, '=') << '\n';

        BPlusTree index(5);

        vector<pair<int, string>> records = {
            {42, "Customer-A"},
            {12, "Customer-B"},
            {89, "Customer-C"},
            {23, "Customer-D"},
            {56, "Customer-E"},
            {78, "Customer-F"},
            {34, "Customer-G"},
            {67, "Customer-H"},
            {91, "Customer-I"},
            {10, "Customer-J"},
            {50, "Customer-K"},
            {72, "Customer-L"},
            {15, "Customer-M"},
            {28, "Customer-N"}
        };

        for (const auto& record : records) {
            index.insert(record.first, record.second);
        }

        cout << "\nSearch 56: " << index.search(56) << '\n';

        cout << "\nSorted traversal:\n";

        for (int key : index.traverse()) {
            cout << key << ' ';
        }

        cout << "\n\nRange scan 20-70:\n";

        for (const auto& record : index.range_scan(20, 70)) {
            cout << record.first << " -> "
                 << record.second << '\n';
        }

        cout << "\nIndex pages:\n";

        for (const auto& page : index.page_report()) {
            cout << "Page " << page.at("page_id")
                 << " [" << page.at("type") << "] "
                 << "Keys=" << page.at("keys")
                 << " Children=" << page.at("children")
                 << " Next=" << page.at("next_leaf")
                 << '\n';
        }

        cout << "\nStatistics:\n";
        index.statistics();

        cout << "\nDeletion and rebalancing:\n";

        for (int key : {10, 12, 15, 23, 28}) {
            index.erase(key);
            assert(index.validate());
        }

        for (int key : index.traverse()) {
            cout << key << ' ';
        }

        cout << "\nTree valid: " << boolalpha
             << index.validate() << '\n';

        cout << "\nBuffer pool simulation:\n";

        BufferPool buffer(4);

        for (const auto& page : index.page_report()) {
            buffer.access(stoi(page.at("page_id")));
        }

        for (const auto& page : index.page_report()) {
            buffer.access(stoi(page.at("page_id")));
        }

        buffer.report();

        cout << "\nRandomized insertion test:\n";

        BPlusTree stress(6);
        vector<int> keys(500);

        for (int i = 0; i < 500; ++i) {
            keys[i] = i;
        }

        mt19937 generator(42);
        shuffle(keys.begin(), keys.end(), generator);

        for (int key : keys) {
            stress.insert(key, "record-" + to_string(key));
        }

        assert(stress.validate());

        auto sorted = stress.traverse();
        assert(is_sorted(sorted.begin(), sorted.end()));
        assert(sorted.size() == 500);

        cout << "500 records inserted and validated.\n";

        for (int i = 0; i < 250; ++i) {
            stress.erase(keys[i]);
        }

        assert(stress.validate());
        cout << "250 deletions validated.\n";

        try {
            index.insert(42, "Duplicate");
        } catch (const invalid_argument& error) {
            cout << "Duplicate rejected: "
                 << error.what() << '\n';
        }

        try {
            index.erase(999);
        } catch (const out_of_range& error) {
            cout << "Missing key rejected: "
                 << error.what() << '\n';
        }

    } catch (const exception& error) {
        cerr << "Execution failed: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
