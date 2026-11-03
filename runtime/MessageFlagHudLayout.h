#pragma once
#include <cstdint>
#include <cstring>
#include <vector>

// Bounded transformation of the selected APMK stream before its first read;
// it neither constructs native objects nor changes resource registrations.
namespace MajestyMessageFlagHud {
constexpr std::uint32_t ToggleControl = 0x7F20;
constexpr std::uint32_t ClearControl = 0x7F21;
constexpr std::size_t MaximumStreamBytes = 1024 * 1024;
constexpr std::uint32_t End = 0xFFFFFFFFu;

struct Property { std::uint32_t token; std::size_t value, count; };
struct Record {
    std::size_t begin, end;
    std::uint32_t type;
    std::vector<Property> properties;
    const Property* Find(std::uint32_t token) const {
        for (const auto& p : properties) if (p.token == token) return &p;
        return nullptr;
    }
};

inline bool Parse(const std::vector<std::uint32_t>& words,
                  std::vector<Record>& records, std::size_t& terminator) {
    std::size_t cursor = 0;
    while (cursor < words.size()) {
        if (words[cursor] == End) { terminator = cursor; return !records.empty(); }
        Record record{cursor, 0, words[cursor++], {}};
        if (record.type > 12 && record.type != 1000) return false;
        while (cursor < words.size() && words[cursor] != End) {
            const auto token = words[cursor++];
            std::size_t count = 1;
            if (token == 2 || token == 42) count = 4;
            else if (token >= 34 && token <= 37) {
                if (cursor == words.size() || words[cursor] > 16) return false;
                count = 1 + words[cursor];
            } else if (!((token >= 3 && token <= 44) || token == 258 || token == 266)) {
                return false;
            }
            if (count > words.size() - cursor) return false;
            record.properties.push_back({token, cursor, count});
            cursor += count;
        }
        if (cursor == words.size()) return false;
        record.end = ++cursor;
        records.push_back(record);
    }
    return false;
}

inline bool Extend(const unsigned char* source, std::size_t size,
                   std::vector<std::uint32_t>& output) {
    output.clear();
    if (!source || size < 8 || size > MaximumStreamBytes || size % 4) return false;
    std::vector<std::uint32_t> words(size / 4);
    std::memcpy(words.data(), source, size);
    std::vector<Record> records;
    std::size_t terminator = 0;
    if (!Parse(words, records, terminator) || records.front().type != 1000) return false;
    const Record* donor = nullptr;
    const Record* text = nullptr;
    for (const auto& record : records) {
        const auto* id = record.Find(6);
        if (!id) continue;
        const auto control = words[id->value];
        if (control == ToggleControl || control == ClearControl) return false;
        if (control == 9005) { if (donor) return false; donor = &record; }
        if (control == 2004) { if (text) return false; text = &record; }
    }
    if (!donor || !text || donor->type != 0 || text->type != 0) return false;
    const auto* box = donor->Find(2);
    const auto* textBox = text->Find(2);
    const auto* captionBox = text->Find(42);
    const auto* image = donor->Find(12);
    const auto* set = donor->Find(13);
    if (!box || !textBox || !captionBox || !image || !set) return false;
    // Stock Options button artwork and geometry; copy its complete native
    // control recipe, including font/color/flags, rather than invent a widget.
    if (words[box->value+2] != 71 || words[box->value+3] != 21 ||
        words[image->value] != 0x7A444E49 || words[set->value] != 1014) return false;
    const auto x = words[box->value], textX = words[textBox->value];
    const auto width = words[textBox->value+2];
    if (x > 32767 || textX > x || width > x-textX) return false;
    const auto gap = x-textX-width;
    if (gap > 16) return false;
    const auto reserve = 2 * (71 + gap);
    if (width <= reserve + 32 || words[captionBox->value+2] <= reserve) return false;
    std::vector<std::uint32_t> additions;
    for (unsigned index=0; index<2; ++index) {
        additions.push_back(donor->type);
        for (const auto& p : donor->properties) {
            // Neither private command inherits Options' Escape shortcuts.
            if (p.token == 5 || p.token == 258 || p.token == 266) continue;
            additions.push_back(p.token);
            for (std::size_t i=0; i<p.count; ++i) {
                auto value = words[p.value+i];
                if (p.token == 2 && i == 0) value = x-reserve+index*(71+gap);
                if (p.token == 6) value = index ? ClearControl : ToggleControl;
                additions.push_back(value);
            }
        }
        additions.push_back(End);
    }
    words[textBox->value+2] -= reserve;
    words[captionBox->value+2] -= reserve;
    words.insert(words.begin()+terminator, additions.begin(), additions.end());
    output.swap(words);
    return true;
}
}
