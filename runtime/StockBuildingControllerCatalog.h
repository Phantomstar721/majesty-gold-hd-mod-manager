#pragma once

#include "MajestyBuildId.h"
#include <cstddef>
#include <cstdint>

// Stock primary-building classes that can safely own manager-added controls.
// This is compiled metadata only: unused entries install no hooks and perform
// no work.  Packages select a FourCC, never an address or vtable length.
namespace MajestyStockBuildingControllers {

struct VtableProfile {
    std::uintptr_t vtableRva;
    std::size_t entryCount;
    std::uintptr_t destructorRva;
    std::uintptr_t setupRva;
    std::uintptr_t controlRva;
    std::uintptr_t eventRva;
};

enum class ControllerClass : std::uint8_t {
    Guild,
    Basic,
    Ap02,
    Ap08,
    Ap17,
    Ap24,
    Ap26,
    Ap31,
    Ap39,
    Ap47,
    Ap48,
    Ap51,
    Ap52,
    Ap53,
    Ap54,
    Apa9,
    Apb8,
    Mx00,
    Mx02,
    Mx04,
    Mx06,
    Mx08,
    Mx09,
    Mx22,
};

struct ClassProfiles {
    VtableProfile publicBuild;
    VtableProfile beta2Build;
};

struct ControllerRecord {
    std::uint32_t controllerId;
    ControllerClass controllerClass;
};

static const ClassProfiles kClassProfiles[] = {
    // Guild: AP01/AP05/AP06/AP07/AP10/AP14/AP19/AP25/AP28.
    {{0x0033D184u, 17, 0x00095F60u, 0x00095BD0u, 0x000968B0u, 0x00096170u},
     {0x00355E5Cu, 17, 0x00096770u, 0x000963E0u, 0x000970C0u, 0x00096980u}},
    // Basic: AP23/AP76/AP96/APb2/APb3/APb7/APc3/APc4.
    {{0x0033D14Cu, 13, 0x00094EE0u, 0x00095990u, 0x00095790u, 0x000959F0u},
     {0x00355E24u, 13, 0x000956F0u, 0x000961A0u, 0x00095FA0u, 0x00096200u}},
    {{0x0033D274u, 13, 0x00099290u, 0x00099530u, 0x000992B0u, 0x00099540u},
     {0x00355F4Cu, 13, 0x00099B70u, 0x00099E10u, 0x00099B90u, 0x00099E20u}},
    {{0x0033D37Cu, 13, 0x0009E2A0u, 0x0009E5D0u, 0x0009E660u, 0x0009E600u},
     {0x00356054u, 13, 0x0009EB80u, 0x0009EEB0u, 0x0009EF40u, 0x0009EEE0u}},
    {{0x0033D4A4u, 13, 0x000A0370u, 0x000A0320u, 0x000A0330u, 0x000A0360u},
     {0x0035617Cu, 13, 0x000A0C50u, 0x000A0C00u, 0x000A0C10u, 0x000A0C40u}},
    {{0x0033E534u, 17, 0x000B17D0u, 0x000B0FA0u, 0x000B1090u, 0x000B15A0u},
     {0x0035720Cu, 17, 0x000B20C0u, 0x000B1890u, 0x000B1980u, 0x000B1E90u}},
    {{0x0033D7B4u, 13, 0x000A4D70u, 0x000A4D90u, 0x000A4DA0u, 0x00096EB0u},
     {0x0035648Cu, 13, 0x000A5670u, 0x000A5690u, 0x000A56A0u, 0x000976C0u}},
    {{0x0033D804u, 14, 0x000A4F00u, 0x000A4F30u, 0x000A5130u, 0x000A4F50u},
     {0x003564DCu, 14, 0x000A5800u, 0x000A5830u, 0x000A5A30u, 0x000A5850u}},
    {{0x0033D888u, 13, 0x000A57C0u, 0x000A5620u, 0x000A5440u, 0x000A56A0u},
     {0x00356560u, 13, 0x000A60C0u, 0x000A5F20u, 0x000A5D40u, 0x000A5FA0u}},
    {{0x0033D8C4u, 17, 0x000A5D50u, 0x000A5B90u, 0x000A5BA0u, 0x000A5CF0u},
     {0x0035659Cu, 17, 0x000A6650u, 0x000A6490u, 0x000A64A0u, 0x000A65F0u}},
    {{0x0033E054u, 17, 0x000AA1B0u, 0x000AA3F0u, 0x000AA400u, 0x00096170u},
     {0x00356D2Cu, 17, 0x000AAAA0u, 0x000AACE0u, 0x000AACF0u, 0x00096980u}},
    {{0x0033E5BCu, 13, 0x000B1D60u, 0x000B1D80u, 0x000B1D90u, 0x000B1DC0u},
     {0x00357294u, 13, 0x000B2650u, 0x000B2670u, 0x000B2680u, 0x000B26B0u}},
    {{0x0033E5F4u, 17, 0x000B1EA0u, 0x000B2010u, 0x000B2170u, 0x000B22C0u},
     {0x003572CCu, 17, 0x000B2790u, 0x000B2900u, 0x000B2A60u, 0x000B2BB0u}},
    {{0x0033E674u, 17, 0x000B3010u, 0x000B3220u, 0x000B3040u, 0x000B3240u},
     {0x0035734Cu, 17, 0x000B3900u, 0x000B3B10u, 0x000B3930u, 0x000B3B30u}},
    {{0x0033E71Cu, 13, 0x000B3A80u, 0x000B3740u, 0x000B3750u, 0x000B37D0u},
     {0x003573F4u, 13, 0x000B4370u, 0x000B4030u, 0x000B4040u, 0x000B40C0u}},
    {{0x0033D784u, 11, 0x000A4B90u, 0x000A4C00u, 0x000A4C30u, 0x000A4C60u},
     {0x0035645Cu, 11, 0x000A5490u, 0x000A5500u, 0x000A5530u, 0x000A5560u}},
    {{0x0033D400u, 11, 0x0009F240u, 0x0009F670u, 0x0009F7C0u, 0x0009F920u},
     {0x003560D8u, 11, 0x0009FB20u, 0x0009FF50u, 0x000A00A0u, 0x000A0200u}},
    {{0x0033E990u, 13, 0x000BADD0u, 0x000BAC70u, 0x000BAA40u, 0x000BAC80u},
     {0x00357678u, 13, 0x000BB810u, 0x000BB6B0u, 0x000BB480u, 0x000BB6C0u}},
    {{0x0033EA34u, 13, 0x000BBAC0u, 0x000BBB20u, 0x000BBB30u, 0x000BBB60u},
     {0x0035771Cu, 13, 0x000BC500u, 0x000BC560u, 0x000BC570u, 0x000BC5A0u}},
    {{0x0033EA6Cu, 13, 0x000BBCC0u, 0x000BBD20u, 0x000BBD30u, 0x000BBD60u},
     {0x00357754u, 13, 0x000BC700u, 0x000BC760u, 0x000BC770u, 0x000BC7A0u}},
    {{0x0033EB64u, 13, 0x000BCEF0u, 0x000BD260u, 0x000BCF50u, 0x000BD220u},
     {0x0035784Cu, 13, 0x000BD930u, 0x000BDCA0u, 0x000BD990u, 0x000BDC60u}},
    {{0x0033EB2Cu, 13, 0x000BCD00u, 0x000BCDA0u, 0x000BCD20u, 0x000BCDD0u},
     {0x00357814u, 13, 0x000BD740u, 0x000BD7E0u, 0x000BD760u, 0x000BD810u}},
    {{0x0033EB9Cu, 13, 0x000BD390u, 0x000BD270u, 0x000BD280u, 0x000BD290u},
     {0x00357884u, 13, 0x000BDDD0u, 0x000BDCB0u, 0x000BDCC0u, 0x000BDCD0u}},
    {{0x0033E91Cu, 17, 0x000B9A30u, 0x000B98A0u, 0x000B9540u, 0x000B98B0u},
     {0x00357604u, 17, 0x000BA470u, 0x000BA2E0u, 0x000B9F80u, 0x000BA2F0u}},
};

static const VtableProfile kGogClassProfiles[] = {
    {0x00354F94u, 17, 0x00096D20u, 0x00096990u, 0x00097670u, 0x00096F30u},
    {0x00354F58u, 13, 0x00095CA0u, 0x00096750u, 0x00096550u, 0x000967B0u},
    {0x00355084u, 13, 0x0009A120u, 0x0009A3C0u, 0x0009A140u, 0x0009A3D0u},
    {0x0035518Cu, 13, 0x0009F130u, 0x0009F460u, 0x0009F4F0u, 0x0009F490u},
    {0x003552B4u, 13, 0x000A1200u, 0x000A11B0u, 0x000A11C0u, 0x000A11F0u},
    {0x00356344u, 17, 0x000B2670u, 0x000B1E40u, 0x000B1F30u, 0x000B2440u},
    {0x003555C4u, 13, 0x000A5C20u, 0x000A5C40u, 0x000A5C50u, 0x00097C70u},
    {0x00355614u, 14, 0x000A5DB0u, 0x000A5DE0u, 0x000A5FE0u, 0x000A5E00u},
    {0x00355698u, 13, 0x000A6670u, 0x000A64D0u, 0x000A62F0u, 0x000A6550u},
    {0x003556D4u, 17, 0x000A6C00u, 0x000A6A40u, 0x000A6A50u, 0x000A6BA0u},
    {0x00355E64u, 17, 0x000AB050u, 0x000AB290u, 0x000AB2A0u, 0x00096F30u},
    {0x003563CCu, 13, 0x000B2C00u, 0x000B2C20u, 0x000B2C30u, 0x000B2C60u},
    {0x00356404u, 17, 0x000B2D40u, 0x000B2EB0u, 0x000B3010u, 0x000B3160u},
    {0x00356484u, 17, 0x000B3EB0u, 0x000B40C0u, 0x000B3EE0u, 0x000B40E0u},
    {0x0035652Cu, 13, 0x000B4920u, 0x000B45E0u, 0x000B45F0u, 0x000B4670u},
    {0x00355594u, 11, 0x000A5A40u, 0x000A5AB0u, 0x000A5AE0u, 0x000A5B10u},
    {0x00355210u, 11, 0x000A00D0u, 0x000A0500u, 0x000A0650u, 0x000A07B0u},
    {0x003567D0u, 13, 0x000BBE10u, 0x000BBCB0u, 0x000BBA80u, 0x000BBCC0u},
    {0x00356874u, 13, 0x000BCB00u, 0x000BCB60u, 0x000BCB70u, 0x000BCBA0u},
    {0x003568ACu, 13, 0x000BCD00u, 0x000BCD60u, 0x000BCD70u, 0x000BCDA0u},
    {0x003569A4u, 13, 0x000BDF30u, 0x000BE2A0u, 0x000BDF90u, 0x000BE260u},
    {0x0035696Cu, 13, 0x000BDD40u, 0x000BDDE0u, 0x000BDD60u, 0x000BDE10u},
    {0x003569DCu, 13, 0x000BE3D0u, 0x000BE2B0u, 0x000BE2C0u, 0x000BE2D0u},
    {0x0035675Cu, 17, 0x000BAA70u, 0x000BA8E0u, 0x000BA580u, 0x000BA8F0u},
};

static const ControllerRecord kControllerRecords[] = {
    {0x31305041u, ControllerClass::Guild},  // AP01
    {0x32305041u, ControllerClass::Ap02},   // AP02
    {0x35305041u, ControllerClass::Guild},  // AP05
    {0x36305041u, ControllerClass::Guild},  // AP06
    {0x37305041u, ControllerClass::Guild},  // AP07
    {0x38305041u, ControllerClass::Ap08},   // AP08
    {0x30315041u, ControllerClass::Guild},  // AP10
    {0x34315041u, ControllerClass::Guild},  // AP14
    {0x37315041u, ControllerClass::Ap17},   // AP17
    {0x39315041u, ControllerClass::Guild},  // AP19
    {0x33325041u, ControllerClass::Basic},  // AP23
    {0x34325041u, ControllerClass::Ap24},   // AP24
    {0x35325041u, ControllerClass::Guild},  // AP25
    {0x36325041u, ControllerClass::Ap26},   // AP26
    {0x38325041u, ControllerClass::Guild},  // AP28
    {0x31335041u, ControllerClass::Ap31},   // AP31
    {0x39335041u, ControllerClass::Ap39},   // AP39
    {0x37345041u, ControllerClass::Ap47},   // AP47
    {0x38345041u, ControllerClass::Ap48},   // AP48
    {0x31355041u, ControllerClass::Ap51},   // AP51
    {0x32355041u, ControllerClass::Ap52},   // AP52
    {0x33355041u, ControllerClass::Ap53},   // AP53
    {0x34355041u, ControllerClass::Ap54},   // AP54
    {0x36375041u, ControllerClass::Basic},  // AP76
    {0x36395041u, ControllerClass::Basic},  // AP96
    {0x39615041u, ControllerClass::Apa9},   // APa9
    {0x32625041u, ControllerClass::Basic},  // APb2
    {0x33625041u, ControllerClass::Basic},  // APb3
    {0x37625041u, ControllerClass::Basic},  // APb7
    {0x38625041u, ControllerClass::Apb8},   // APb8
    {0x33635041u, ControllerClass::Basic},  // APc3
    {0x34635041u, ControllerClass::Basic},  // APc4
    {0x3030584Du, ControllerClass::Mx00},   // MX00
    {0x3230584Du, ControllerClass::Mx02},   // MX02
    {0x3430584Du, ControllerClass::Mx04},   // MX04
    {0x3630584Du, ControllerClass::Mx06},   // MX06
    {0x3830584Du, ControllerClass::Mx08},   // MX08
    {0x3930584Du, ControllerClass::Mx09},   // MX09
    {0x3232584Du, ControllerClass::Mx22},   // MX22
};

inline const ControllerRecord* Find(std::uint32_t controllerId) {
    for (std::size_t index = 0;
         index < sizeof(kControllerRecords) / sizeof(kControllerRecords[0]);
         ++index) {
        if (kControllerRecords[index].controllerId == controllerId) {
            return &kControllerRecords[index];
        }
    }
    return nullptr;
}

inline const VtableProfile* Profile(
    const ControllerRecord* record, MajestyBuildId buildId) {
    if (record == nullptr) return nullptr;
    const std::size_t index = static_cast<std::size_t>(record->controllerClass);
    if (index >= sizeof(kClassProfiles) / sizeof(kClassProfiles[0])) return nullptr;
    switch (buildId) {
    case MajestyBuildId::SteamPublic: return &kClassProfiles[index].publicBuild;
    case MajestyBuildId::SteamBeta2: return &kClassProfiles[index].beta2Build;
    case MajestyBuildId::Gog: return &kGogClassProfiles[index];
    default: return nullptr;
    }
}

inline bool IsSupported(std::uint32_t controllerId) {
    return Find(controllerId) != nullptr;
}

}  // namespace MajestyStockBuildingControllers
