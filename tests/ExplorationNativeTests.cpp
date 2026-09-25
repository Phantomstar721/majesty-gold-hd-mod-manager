// Execute our x86 trampoline against synthetic tile masks, never game code.
#include "../runtime/MajestyModManagerRuntime.cpp"
#include <cstdio>
#include <chrono>

namespace {
std::uint32_t actualEax, actualEcx, actualEbx, actualEsi;
__declspec(naked) void ResumeTile() {
    __asm {
        cmp eax, ecx
        ret
    }
}
void InvokeTile(std::uint32_t* tile, std::uint32_t mask) {
    __asm {
        push ebx
        push esi
        push edi
        mov edi, tile
        mov ebx, 12345678h
        mov esi, 76543210h
        mov eax, mask
        sub esp, 44h
        mov [esp+40h], eax
        call ExplorationObservation::TileWrite
        mov actualEax, eax
        mov actualEcx, ecx
        mov actualEbx, ebx
        mov actualEsi, esi
        add esp, 44h
        pop edi
        pop esi
        pop ebx
    }
}
bool Check(bool value, const char* message) {
    if (!value) std::fprintf(stderr, "Exploration native failure: %s\n", message);
    return value;
}
}

int main() {
    using namespace ExplorationObservation;
    tileResume = reinterpret_cast<std::uintptr_t>(&ResumeTile);
    bool okay = true;
    Batch observed{4, 0};
    for (auto oldMask : {0u, 4u, 8u, 0x80000000u, 0xFFFFFFFFu}) {
        for (auto newBits : {0u, 4u, 12u, 0x80000000u}) {
            for (int mode = 0; mode < 3; ++mode) {
                batch = mode == 2 ? &observed : nullptr;
                activeBatches = mode != 0; // Mode 1: another thread's batch.
                observed.tiles = 0;
                auto tile = oldMask;
                InvokeTile(&tile, newBits);
                okay = Check(actualEax == (oldMask | newBits) && actualEcx == oldMask,
                             "displaced register results") && okay;
                okay = Check(actualEbx == 0x12345678 && actualEsi == 0x76543210,
                             "preserved registers") && okay;
                okay = Check(tile == oldMask, "stock write remains outside trampoline") && okay;
                const int expected = mode == 2 && !(oldMask & 4) && (newBits & 4);
                okay = Check(observed.tiles == expected, "owner-only zero-to-one count") && okay;
            }
        }
    }
    if (!okay) return 1;
    // Synthetic hot-path measurement only; excludes GPL delivery and the game.
    constexpr int iterations = 1000000;
    for (int mode = 0; mode < 2; ++mode) {
        batch = mode ? &observed : nullptr;
        activeBatches = mode;
        observed.tiles = 0;
        std::uint32_t tile = 0;
        const auto start = std::chrono::steady_clock::now();
        for (int i = 0; i < iterations; ++i) InvokeTile(&tile, 4);
        const auto elapsed = std::chrono::duration<double, std::nano>(
            std::chrono::steady_clock::now()-start).count()/iterations;
        std::printf("synthetic tile interception %s: %.1f ns/call\n",
                    mode ? "observed" : "inactive", elapsed);
    }
    batch = nullptr;
    activeBatches = 0;
    return 0;
}
