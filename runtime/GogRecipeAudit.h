#pragma once
#include "GogAuditedRanges.h"
namespace MajestyGogAudit {
constexpr Range kRecipes[] = {
    {0x00025B70, 137, 0xEBE9FA29u, 0, 0}, // dialog creation
    {0x0010D060, 5201, 0x85251067u, 5183, 18}, // dialog factory
    {0x00025F60, 108, 0xFE738D26u, 0, 0}, // uiManagerRva
    {0x00025AE0, 132, 0xF39B0025u, 0, 0}, // removeDialogRva
    {0x000686A0, 19, 0x0F9D96ABu, 0, 0}, // selectedAgentRva
    {0x001D6590, 40, 0x81925BCFu, 0, 0}, // getCommandMetadataRva
    {0x0002A390, 44, 0xB2EB1635u, 0, 0}, // getPlayerAgentRva
    {0x001CE2C0, 33, 0x0CDE635Bu, 0, 0}, // movement packed attribute
    {0x000C5CF0, 205, 0x7D2706AAu, 0, 0}, // submitBuildingCommandRva
    {0x000C5DE0, 2424, 0x9EC6B6F8u, 0, 0}, // rageCommandDispatchRva
    {0x000B20E0, 245, 0x2D0A8A74u, 0, 0}, // rageGplConstructionResumeRva
    {0x00025480, 244, 0xCC5B4D4Au, 0, 0}, // gameUpdateCallRva
    {0x000A9980, 180, 0x1AC4D285u, 0, 0}, // canSubmitResearchRva
    {0x000A9710, 610, 0xE1BF73E5u, 0, 0}, // refreshSingleResearchRowRva
    {0x000E0B70, 588, 0xD5254490u, 0, 0}, // researchCompletionNamePushRva
    {0x000A9580, 100, 0x90394A8Cu, 0, 0}, // resolveResearchDescriptorRva
    {0x000AF250, 100, 0xB40B0028u, 0, 0}, // resolveSpellDescriptorRva
    {0x000AF370, 226, 0xC1F1761Fu, 0, 0}, // refreshSingleSpellRowRva
    {0x00024C60, 22, 0xA6279F79u, 0, 0}, // getCurrentPlayerRva
    {0x000A41B0, 3832, 0xB0D8F7C2u, 0, 0}, // enchantment rows
    {0x0023CC40, 145, 0x4B93B085u, 0, 0}, // stock string assignment
    {0x0010ADE0, 67, 0x0BE57809u, 0, 0}, // intent resolver
    {0x00174330, 9, 0xA5E6C345u, 0, 0}, // intent provider
    {0x00112650, 1857, 0x6F36E33Bu, 0, 0}, // name registry
    {0x0010E4D0, 177, 0x9875D48Eu, 0, 0}, // name factory
    {0x0010CFD0, 131, 0x32971D7Cu, 0, 0}, // name construction
    {0x00111FD0, 169, 0x24E80563u, 0, 0}, // name insertion
    {0x000AF2C0, 85, 0xA25507F3u, 0, 0}, // sovereignSpellClickRva
    {0x0005F520, 142, 0x0FD1FDB7u, 0, 0}, // sovereignTargetManagerRva
    {0x0005F920, 85, 0x145F440Du, 0, 0}, // sovereignTargetCancelRva
    {0x0005FD00, 269, 0x9CD32E12u, 0, 0}, // sovereignCursorTransitionRva
    {0x00066BB0, 1334, 0x46811F8Cu, 0, 0}, // sovereignTargetCommitCallRva
    {0x000DACC0, 174, 0x2F1044E8u, 0, 0}, // sovereignSubmitCommandRva
    {0x000DAD70, 3800, 0x85FB9E7Eu, 0, 0}, // sovereignConstructionOverrideRva
    {0x000B1290, 218, 0xF80E1518u, 0, 0}, // openDialogRva
    {0x000AA0D0, 618, 0x6511EA1Bu, 0, 0}, // stockAp41ActivationRva
    {0x000AA340, 202, 0x7BA12A63u, 0, 0}, // stockAp41RefreshRva
    {0x00055DC0, 121, 0x1DA79D0Du, 0, 0}, // setFlagModeRva
    {0x0005E8F0, 2902, 0x7EF31E48u, 0, 0}, // modeRegistryResumeRva
    {0x0005E350, 466, 0xB2A0B0B7u, 0, 0}, // stockCaptureCallbackRva
    {0x0005E2B0, 157, 0x60344D62u, 0, 0}, // stockCaptureValidatorRva
    {0x0005E220, 130, 0x4A3EA01Bu, 0, 0}, // stockFlagTargetCheckRva
    {0x0010AE70, 766, 0x9DA0566Eu, 0, 0}, // display classifier
    {0x001BBA30, 499, 0x2DDD5A18u, 0, 0}, // findAttachedRelationRva
    {0x0006BD90, 27, 0xC27A049Fu, 0, 0}, // prepareSystemAlertRva
    {0x0006BF00, 109, 0x0BDB9EA9u, 0, 0}, // postLiteralSystemAlertRva
    {0x001B14E0, 60, 0x0A0ADFEDu, 0, 0}, // flagModeConstructorRva
    {0x001B3230, 108, 0x23C45FC0u, 0, 0}, // getFlagModeRegistryRva
    {0x000C3CA0, 120, 0x755B1BEFu, 0, 0}, // submitResearchCommandRva
    {0x00055AE0, 19, 0x5AA774D4u, 0, 0}, // getFlagModeManagerRva
    {0x00056620, 4, 0x6915AB30u, 0, 0}, // getSelectedFlagModeRva
    {0x00267DA0, 117, 0xBD427928u, 0, 0}, // stream control lookup
    {0x00268260, 461, 0x53F0B0C8u, 0, 0}, // stream message
    {0x002D0400, 115, 0x7EA9E86Cu, 0, 0}, // list construction
    {0x002D0480, 146, 0xD6A8EC44u, 0, 0}, // list destructor
    {0x000BD210, 177, 0xF0E8AD8Bu, 0, 0}, // occupant child refresh
    {0x000BD320, 377, 0xDBB3BDB1u, 0, 0}, // occupant child construction
    {0x000BCFF0, 533, 0xDC71F69Fu, 0, 0}, // occupant child control
    {0x00099B50, 616, 0x824D48B2u, 0, 0}, // occupant shared control
    {0x000BCDF0, 156, 0xB25F348Au, 0, 0}, // list evaluator helper
    {0x00178AB0, 218, 0x5EBDB50Cu, 0, 0}, // list evaluator construction
    {0x00178070, 8, 0xBF6E4C50u, 0, 0}, // list evaluator agent
    {0x00178090, 8, 0x0D2A34F1u, 0, 0}, // list evaluator integer
    {0x00178BF0, 579, 0x8DE4ABAAu, 0, 0}, // list evaluator execute
    {0x00178950, 22, 0xEB5A9B42u, 0, 0}, // list evaluator scalar
    {0x00178B90, 26, 0x9D2B0622u, 0, 0}, // list evaluator destruction
    {0x0023C520, 33, 0x788DA9A2u, 0, 0}, // registration string destruction
    {0x000430E0, 521, 0x074EF835u, 0, 0}, // list name formatter
    {0x00098F40, 1945, 0xD56FF718u, 0, 0}, // visitor painter
    {0x00024280, 41, 0x5CCB1DB3u, 0, 0}, // list summary resolver
    {0x002871A0, 34, 0x6316A0A7u, 0, 0}, // list status painter
    {0x00098BF0, 733, 0xDC42BC4Cu, 0, 0}, // list shared refresh
    {0x00096B10, 116, 0x623F9204u, 0, 0}, // recruit produced
    {0x00096D20, 284, 0x051C57EAu, 0, 0}, // controller method 0x96770
    {0x00096E40, 168, 0x97C929C8u, 0, 0}, // recruit quote
    {0x00097060, 58, 0xC9800F5Cu, 0, 0}, // recruit affordable
    {0x00096EF0, 55, 0xF0CE326Au, 0, 0}, // recruit tooltip price
    {0x000B31C0, 281, 0x7CCF180Du, 0, 0}, // recruit counts
    {0x000B2DF0, 182, 0x1A3C1B68u, 0, 0}, // recruit call to arms
    {0x000E0A30, 305, 0x31071BD4u, 0, 0}, // research executor
    {0x000B4E70, 284, 0xACAAD663u, 0, 0}, // stream adapter construction
    {0x000B5D80, 577, 0xEF049FFBu, 0, 0}, // stream derived construction
    {0x00272890, 41, 0x0520CD90u, 0, 0}, // list messages
    {0x000B4C40, 10, 0x151A0B4Du, 0, 0}, // stream adapter 0x14
    {0x000B4BC0, 110, 0x7067FF9Du, 0, 0}, // stream adapter 0x20
    {0x000B5330, 261, 0x01734DAFu, 0, 0}, // stream adapter 0x28
    {0x000B5640, 30, 0xD64DAA54u, 0, 0}, // stream adapter 0x34
    {0x000B5770, 27, 0x59D9015Du, 0, 0}, // stream adapter 0x50
    {0x000B5750, 27, 0x59D9015Du, 0, 0}, // stream adapter 0x54
    {0x000B5730, 27, 0x834A11F0u, 0, 0}, // stream adapter 0x58
    {0x000B5790, 30, 0x6D5D4BB4u, 0, 0}, // stream adapter 0x5c
    {0x000B4C50, 10, 0x0FB18A67u, 0, 0}, // stream adapter 0x68
    {0x00026BF0, 969, 0x724075A6u, 0, 0}, // game state update
    {0x003D46D8, 12, 0x3BF415D0u, 0, 0}, // research completion dispatch
    {0x00356590, 4, 0x09590372u, 0, 0}, // stream virtual 0x14
    {0x00356658, 4, 0x09590372u, 0, 0}, // derived stream virtual 0x14
    {0x0035659C, 4, 0x7E25230Fu, 0, 0}, // stream virtual 0x20
    {0x00356664, 4, 0x7E25230Fu, 0, 0}, // derived stream virtual 0x20
    {0x003565A4, 4, 0x61FF9297u, 0, 0}, // stream virtual 0x28
    {0x0035666C, 4, 0x61FF9297u, 0, 0}, // derived stream virtual 0x28
    {0x003565B0, 4, 0xFD894D60u, 0, 0}, // stream virtual 0x34
    {0x00356678, 4, 0xFD894D60u, 0, 0}, // derived stream virtual 0x34
    {0x003565D0, 4, 0x87D3B51Bu, 0, 0}, // stream virtual 0x50
    {0x00356698, 4, 0x87D3B51Bu, 0, 0}, // derived stream virtual 0x50
    {0x003565D4, 4, 0xF5A5787Bu, 0, 0}, // stream virtual 0x54
    {0x0035669C, 4, 0xF5A5787Bu, 0, 0}, // derived stream virtual 0x54
    {0x003565D8, 4, 0x04FFEA5Bu, 0, 0}, // stream virtual 0x58
    {0x003566A0, 4, 0x04FFEA5Bu, 0, 0}, // derived stream virtual 0x58
    {0x003565DC, 4, 0x75FEDA3Bu, 0, 0}, // stream virtual 0x5c
    {0x003566A4, 4, 0x75FEDA3Bu, 0, 0}, // derived stream virtual 0x5c
    {0x003565F0, 4, 0x7F769A02u, 0, 0}, // stream virtual 0x68
    {0x003566B8, 4, 0x7F769A02u, 0, 0}, // derived stream virtual 0x68
    {0x003687A0, 4, 0x6C230A92u, 0, 0}, // list message virtual
    {0x00356904, 60, 0xB86452FFu, 0, 0}, // occupant child vtable
    {0x000AD4C0, 433, 0x34F3C98Du, 0, 0}, // secondary lifecycle 0xad000
    {0x000A8990, 296, 0x69EB7F27u, 0, 0}, // secondary lifecycle 0xa83e0
    {0x000A84D0, 90, 0xBD583F03u, 0, 0}, // secondary lifecycle 0xa7f40
    {0x000A85E0, 169, 0xBBE2C503u, 0, 0}, // secondary lifecycle 0xa8030
    {0x000ABE60, 30, 0xD2A69BD2u, 0, 0}, // AP69 method 0xab8b0
    {0x000AF560, 39, 0x6C2E9D84u, 0, 0}, // AP69 method 0xaefb0
    {0x000AF320, 69, 0x5701DC62u, 0, 0}, // AP69 method 0xaed70
    {0x000AF590, 554, 0xAB0C82D0u, 0, 0}, // AP69 method 0xaefe0
    {0x00095BE0, 8, 0x3B587B28u, 0, 0}, // controller method 0x95630
    {0x00095BF0, 23, 0xBDE07F4Eu, 0, 0}, // controller method 0x95640
    {0x000B02B0, 139, 0x489F61D1u, 0, 0}, // controller method 0xafd00
    {0x000AF930, 165, 0xFE9A4EF0u, 0, 0}, // controller method 0xaf380
    {0x000AF7C0, 66, 0x25407AD4u, 0, 0}, // AP69 method 0xaf210
    {0x000AFF30, 179, 0xE4DE1000u, 0, 0}, // controller method 0xaf980
    {0x000B01C0, 161, 0xD45A04ABu, 0, 0}, // controller method 0xafc10
    {0x00355F10, 44, 0x5E1D7102u, 0, 0}, // AP69 vtable
};
} // namespace MajestyGogAudit
