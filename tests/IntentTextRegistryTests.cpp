#include "../runtime/IntentTextRegistry.h"

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace {

void AppendU32(std::vector<unsigned char>* bytes, std::uint32_t value) {
    bytes->push_back(static_cast<unsigned char>(value & 0xFF));
    bytes->push_back(static_cast<unsigned char>((value >> 8) & 0xFF));
    bytes->push_back(static_cast<unsigned char>((value >> 16) & 0xFF));
    bytes->push_back(static_cast<unsigned char>((value >> 24) & 0xFF));
}

void AppendRecord(
    std::vector<unsigned char>* bytes,
    std::uint32_t id,
    const std::vector<unsigned char>& text) {
    AppendU32(bytes, id);
    AppendU32(bytes, static_cast<std::uint32_t>(text.size()));
    bytes->insert(bytes->end(), text.begin(), text.end());
}

std::vector<unsigned char> Header(std::uint32_t version, std::uint32_t count) {
    std::vector<unsigned char> bytes = {'M', 'M', 'T', 'X'};
    AppendU32(&bytes, version);
    AppendU32(&bytes, count);
    return bytes;
}

bool ExpectValid(const std::vector<unsigned char>& bytes) {
    std::vector<MajestyIntentText::RegistryRecord> records;
    std::string error;
    if (!MajestyIntentText::ParseRegistry(
            bytes.data(), bytes.size(), &records, &error)) {
        std::fprintf(stderr, "Expected valid registry: %s\n", error.c_str());
        return false;
    }
    return records.size() == 2 &&
        records[0].id == 0x60000010u &&
        records[0].text == "Applying weapon oil at the alchemy lab" &&
        records[1].id == 0x6FFFFFF0u &&
        records[1].text.size() == 4 &&
        static_cast<unsigned char>(records[1].text[3]) == 0xE9;
}

bool ExpectInvalid(
    const std::vector<unsigned char>& bytes,
    const char* expectedErrorPart) {
    std::vector<MajestyIntentText::RegistryRecord> records;
    std::string error;
    if (MajestyIntentText::ParseRegistry(
            bytes.data(), bytes.size(), &records, &error)) {
        std::fprintf(stderr, "Expected registry rejection.\n");
        return false;
    }
    if (error.find(expectedErrorPart) == std::string::npos) {
        std::fprintf(
            stderr,
            "Wrong registry rejection: expected '%s', got '%s'.\n",
            expectedErrorPart,
            error.c_str());
        return false;
    }
    return records.empty();
}

}  // namespace

int main() {
    std::vector<unsigned char> valid = Header(1, 2);
    AppendRecord(
        &valid,
        0x60000010u,
        std::vector<unsigned char>{
            'A','p','p','l','y','i','n','g',' ','w','e','a','p','o','n',' ',
            'o','i','l',' ','a','t',' ','t','h','e',' ','a','l','c','h','e','m','y',' ',
            'l','a','b'});
    AppendRecord(
        &valid,
        0x6FFFFFF0u,
        std::vector<unsigned char>{'c','a','f',0xE9});
    if (!ExpectValid(valid)) {
        return 1;
    }

    std::vector<unsigned char> badMagic = valid;
    badMagic[0] = 'X';
    if (!ExpectInvalid(badMagic, "magic")) {
        return 2;
    }
    std::vector<unsigned char> badVersion = valid;
    badVersion[4] = 2;
    if (!ExpectInvalid(badVersion, "version")) {
        return 3;
    }
    std::vector<unsigned char> lowId = Header(1, 1);
    AppendRecord(&lowId, 309, std::vector<unsigned char>{'x'});
    if (!ExpectInvalid(lowId, "private range")) {
        return 4;
    }
    std::vector<unsigned char> duplicate = Header(1, 2);
    AppendRecord(&duplicate, 0x60000010u, std::vector<unsigned char>{'a'});
    AppendRecord(&duplicate, 0x60000010u, std::vector<unsigned char>{'b'});
    if (!ExpectInvalid(duplicate, "strictly increasing")) {
        return 5;
    }
    std::vector<unsigned char> nulText = Header(1, 1);
    AppendRecord(&nulText, 0x60000010u, std::vector<unsigned char>{'a',0,'b'});
    if (!ExpectInvalid(nulText, "Windows-1252")) {
        return 6;
    }
    std::vector<unsigned char> undefinedCp1252 = Header(1, 1);
    AppendRecord(
        &undefinedCp1252,
        0x60000010u,
        std::vector<unsigned char>{0x81});
    if (!ExpectInvalid(undefinedCp1252, "Windows-1252")) {
        return 7;
    }
    std::vector<unsigned char> trailing = valid;
    trailing.push_back(0);
    if (!ExpectInvalid(trailing, "trailing")) {
        return 8;
    }
    std::vector<unsigned char> truncated = valid;
    truncated.pop_back();
    if (!ExpectInvalid(truncated, "truncated")) {
        return 9;
    }
    std::vector<unsigned char> empty = Header(1, 0);
    std::vector<MajestyIntentText::RegistryRecord> emptyRecords;
    std::string emptyError;
    if (!MajestyIntentText::ParseRegistry(
            empty.data(), empty.size(), &emptyRecords, &emptyError) ||
        !emptyRecords.empty()) {
        std::fprintf(stderr, "Expected an empty MMTX registry to be valid.\n");
        return 10;
    }

    std::puts("Intent-text registry parser tests passed.");
    return 0;
}
