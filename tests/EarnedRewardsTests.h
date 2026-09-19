#pragma once
namespace RewardsTest {
void Run() {
    using namespace MajestyEarnedRewards;
    const int maximum = (std::numeric_limits<int>::max)();
    for (int base : {1, 5, 99, 100, 1000, 2000000000, maximum}) {
        assert(CapAdd(base, 0) == base);
        assert(CapAdd(base, -1) == base);
        for (int percent : {0, 1, 15, 100}) {
            int carry = 31;
            const int bonus = Bonus(base, percent, carry);
            assert(bonus == std::int64_t(base)*percent/100 +
                ((std::int64_t(base)*percent%100)+31)/100);
            assert(carry == (std::int64_t(base)*percent+31)%100);
            assert(CapAdd(base, bonus) >= base);
        }
    }
    assert(CapAdd(maximum, maximum) == maximum);
    assert(CapAdd(-1, 15) == -1);
    int carry = 0, total = 0;
    for (int i = 0; i < 100; ++i) total += CapAdd(1, Bonus(1, 15, carry));
    assert(total == 115 && carry == 0);
    carry = 90;
    assert(Bonus(0, 15, carry) == 0 && carry == 90);
    assert(Bonus(-1, 15, carry) == 0 && carry == 90);
    assert(Bonus(1, 15, carry) == 1 && carry == 5);
    for (int invalid : {-1, 100, maximum}) {
        carry = invalid;
        assert(Bonus(10, 15, carry) == 0 && carry == invalid);
    }
    carry = 90;
    assert(Bonus(10, 101, carry) == 0 && carry == 90);

    // Exercise the production callbacks through stock-shaped x86 GPL slots,
    // including in/out variable storage and return/input aliasing.
    using namespace NativeTest;
    void* table[24] = {};
    table[0x28/4] = reinterpret_cast<void*>(&AsInt);
    Value values[4] = {{table,1,-999,0},{table,1,5,0},
                       {table,1,0,0},{table,1,90,0}};
    void* objects[4]; void** entries[4];
    for (int i = 0; i < 4; ++i) { objects[i] = &values[i]; entries[i] = &objects[i]; }
    Args args{nullptr,{},entries,entries+4};
    Profile profile = kBeta;
    profile.argumentAt = reinterpret_cast<std::uintptr_t>(&At);
    g_base = 0; g_profile = &profile;
    ResearchCapAdd(&args);
    assert(values[0].x == 5); // formerly INT_MAX, even with no active bonus
    entries[0] = entries[1];
    values[2].x = 15;
    ResearchAwardBonus(&args);
    assert(values[1].x == 1 && values[3].x == 65);
    values[1].x = 5; values[2].x = 1;
    ResearchCapAdd(&args);
    assert(values[1].x == 6);
    entries[0] = &objects[0];
    args.end = args.first+3;
    ResearchAwardBonus(&args);
    assert(values[0].x == 0 && values[3].x == 65);
    g_profile = nullptr;
}
}
