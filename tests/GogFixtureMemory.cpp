// A dedicated, non-executable section reserves the game's address as part of
// the test process image, before Windows creates heaps or loads dependencies.
// The test builder pins this section to 0x400000 without changing game files.
#pragma section(".fixture", read, write)
extern "C" __declspec(allocate(".fixture")) unsigned char GogFixtureBytes[0x500000] = {};
