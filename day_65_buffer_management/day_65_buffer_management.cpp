#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <list>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using PageId = std::uint64_t;

enum class PageState {
    Clean,
    Dirty
};

struct Page {
    PageId id;
    std::string data;
    std::size_t pinCount = 0;
    PageState state = PageState::Clean;
    std::uint64_t accessCount = 0;
};

struct Statistics {
    std::uint64_t requests = 0;
    std::uint64_t hits = 0;
    std::uint64_t misses = 0;
    std::uint64_t evictions = 0;
    std::uint64_t writes = 0;
    std::uint64_t failedEvictions = 0;

    double hitRatio() const {
        return requests == 0
            ? 0.0
            : static_cast<double>(hits) / requests;
    }
};

class StorageManager {
private:
    std::unordered_map<PageId, std::string> disk_;
    std::size_t pageSize_;

public:
    explicit StorageManager(std::size_t pageSize)
        : pageSize_(pageSize) {
        if (pageSize == 0) {
            throw std::invalid_argument("Page size must be positive.");
        }
    }

    std::string read(PageId id) {
        if (disk_.find(id) == disk_.end()) {
            std::string initial = "DATABASE_PAGE_" + std::to_string(id);
            initial.resize(pageSize_, '\0');
            disk_[id] = initial;
        }

        return disk_.at(id);
    }

    void write(PageId id, const std::string& data) {
        if (data.size() != pageSize_) {
            throw std::invalid_argument("Invalid storage page size.");
        }

        disk_[id] = data;
    }

    bool contains(PageId id) const {
        return disk_.find(id) != disk_.end();
    }
};

class BufferPool {
private:
    using LruList = std::list<PageId>;

    struct Frame {
        Page page;
        LruList::iterator position;
    };

    std::size_t capacity_;
    std::size_t pageSize_;
    StorageManager& storage_;

    std::unordered_map<PageId, Frame> frames_;
    LruList lru_;
    Statistics stats_;

    void validate(PageId id) const {
        if (id > 1000000000000ULL) {
            throw std::out_of_range("Page ID exceeds supported range.");
        }
    }

    void flushFrame(Page& page) {
        if (page.state == PageState::Dirty) {
            storage_.write(page.id, page.data);
            page.state = PageState::Clean;
            stats_.writes++;
        }
    }

    void evict() {
        auto candidate = lru_.rbegin();

        while (candidate != lru_.rend()) {
            PageId id = *candidate;
            auto frame = frames_.find(id);

            if (frame != frames_.end() &&
                frame->second.page.pinCount == 0) {

                flushFrame(frame->second.page);

                auto listPosition = frame->second.position;
                frames_.erase(frame);
                lru_.erase(listPosition);

                stats_.evictions++;
                return;
            }

            ++candidate;
        }

        stats_.failedEvictions++;

        throw std::runtime_error(
            "Buffer pool exhausted: every frame is pinned."
        );
    }

    void updateLru(Frame& frame) {
        lru_.erase(frame.position);
        lru_.push_front(frame.page.id);
        frame.position = lru_.begin();
    }

public:
    BufferPool(
        std::size_t capacity,
        std::size_t pageSize,
        StorageManager& storage
    )
        : capacity_(capacity),
          pageSize_(pageSize),
          storage_(storage) {

        if (capacity == 0 || pageSize == 0) {
            throw std::invalid_argument(
                "Capacity and page size must be positive."
            );
        }
    }

    Page& fetch(PageId id) {
        validate(id);
        stats_.requests++;

        auto existing = frames_.find(id);

        if (existing != frames_.end()) {
            stats_.hits++;
            existing->second.page.accessCount++;
            updateLru(existing->second);
            return existing->second.page;
        }

        stats_.misses++;

        // Read storage before eviction so failed reads preserve cached pages.
        std::string data = storage_.read(id);

        if (data.size() != pageSize_) {
            throw std::runtime_error("Storage returned an invalid page.");
        }

        if (frames_.size() >= capacity_) {
            evict();
        }

        lru_.push_front(id);

        Page page;
        page.id = id;
        page.data = std::move(data);
        page.accessCount = 1;

        auto [iterator, inserted] = frames_.emplace(
            id,
            Frame{std::move(page), lru_.begin()}
        );

        if (!inserted) {
            lru_.pop_front();
            throw std::runtime_error("Duplicate buffer frame.");
        }

        return iterator->second.page;
    }

    Page& pin(PageId id) {
        Page& page = fetch(id);
        page.pinCount++;
        return page;
    }

    void unpin(PageId id, bool dirty = false) {
        auto iterator = frames_.find(id);

        if (iterator == frames_.end()) {
            throw std::runtime_error("Page is not cached.");
        }

        Page& page = iterator->second.page;

        if (page.pinCount == 0) {
            throw std::runtime_error("Page is not pinned.");
        }

        page.pinCount--;

        if (dirty) {
            page.state = PageState::Dirty;
        }
    }

    void modify(
        PageId id,
        std::size_t offset,
        const std::string& value
    ) {
        if (offset > pageSize_ ||
            value.size() > pageSize_ - offset) {
            throw std::out_of_range("Write exceeds page boundaries.");
        }

        Page& page = pin(id);

        try {
            page.data.replace(offset, value.size(), value);
            unpin(id, true);
        } catch (...) {
            unpin(id, false);
            throw;
        }
    }

    void flush(PageId id) {
        auto iterator = frames_.find(id);

        if (iterator == frames_.end()) {
            throw std::runtime_error("Page is not cached.");
        }

        Page& page = iterator->second.page;

        if (page.pinCount > 0) {
            throw std::runtime_error("Cannot flush a pinned page.");
        }

        flushFrame(page);
    }

    void flushAll() {
        for (const auto& entry : frames_) {
            if (entry.second.page.pinCount > 0) {
                throw std::runtime_error(
                    "Cannot flush all pages while a page is pinned."
                );
            }
        }

        for (auto& entry : frames_) {
            flushFrame(entry.second.page);
        }
    }

    void invalidate(PageId id, bool discardDirty = false) {
        auto iterator = frames_.find(id);

        if (iterator == frames_.end()) {
            return;
        }

        Page& page = iterator->second.page;

        if (page.pinCount > 0) {
            throw std::runtime_error("Cannot invalidate a pinned page.");
        }

        if (!discardDirty) {
            flushFrame(page);
        }

        lru_.erase(iterator->second.position);
        frames_.erase(iterator);
    }

    void display() const {
        std::cout << "\nBUFFER POOL STATUS\n";
        std::cout << "Capacity: " << capacity_ << '\n';
        std::cout << "Occupied: " << frames_.size() << '\n';

        std::cout << "\nPage ID | State | Pins | Accesses\n";
        std::cout << "---------------------------------\n";

        for (PageId id : lru_) {
            const Page& page = frames_.at(id).page;

            std::cout
                << page.id << " | "
                << (page.state == PageState::Dirty ? "DIRTY" : "CLEAN")
                << " | "
                << page.pinCount << " | "
                << page.accessCount << '\n';
        }

        std::cout << "\nSTATISTICS\n";
        std::cout << "Requests: " << stats_.requests << '\n';
        std::cout << "Hits: " << stats_.hits << '\n';
        std::cout << "Misses: " << stats_.misses << '\n';
        std::cout << "Evictions: " << stats_.evictions << '\n';
        std::cout << "Writes: " << stats_.writes << '\n';
        std::cout << "Failed evictions: "
                  << stats_.failedEvictions << '\n';

        std::cout << "Hit ratio: "
                  << std::fixed << std::setprecision(2)
                  << stats_.hitRatio() * 100.0 << "%\n";
    }

    const Statistics& statistics() const {
        return stats_;
    }
};

int main() {
    try {
        constexpr std::size_t PAGE_SIZE = 64;

        StorageManager storage(PAGE_SIZE);

        BufferPool pool(
            3,
            PAGE_SIZE,
            storage
        );

        std::cout << "DATABASE BUFFER MANAGEMENT\n";

        std::cout << "\n1. Load database pages\n";

        pool.fetch(100);
        pool.fetch(200);
        pool.fetch(300);

        std::cout << "\n2. Access an existing page\n";

        pool.fetch(100);
        pool.fetch(200);

        std::cout << "\n3. Modify a database record\n";

        pool.modify(200, 0, "UPDATED_CUSTOMER_RECORD");

        std::cout << "\n4. Trigger LRU eviction\n";

        pool.fetch(400);

        std::cout << "\n5. Demonstrate pinning\n";

        pool.pin(100);
        pool.pin(300);
        pool.pin(400);

        try {
            pool.fetch(500);
        } catch (const std::exception& error) {
            std::cout << "Expected failure: "
                      << error.what() << '\n';
        }

        pool.unpin(100);
        pool.unpin(300);
        pool.unpin(400);

        std::cout << "\n6. Persist dirty pages\n";

        pool.flushAll();

        std::cout << "\n7. Display buffer statistics\n";

        pool.display();

        std::cout << "\n8. Verify persistence\n";

        if (!storage.contains(200)) {
            throw std::runtime_error("Page persistence failed.");
        }

        if (pool.statistics().hits == 0 ||
            pool.statistics().misses == 0) {
            throw std::runtime_error("Statistics validation failed.");
        }

        std::cout << "All assertions passed.\n";

    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
