#include "../runtime/StockControllerRegistry.h"

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace {

std::uint32_t FourCC(const char value[5]) {
    return static_cast<std::uint32_t>(value[0]) |
        (static_cast<std::uint32_t>(value[1]) << 8) |
        (static_cast<std::uint32_t>(value[2]) << 16) |
        (static_cast<std::uint32_t>(value[3]) << 24);
}

void AppendU32(std::vector<unsigned char>* bytes, std::uint32_t value) {
    bytes->push_back(static_cast<unsigned char>(value & 0xFF));
    bytes->push_back(static_cast<unsigned char>((value >> 8) & 0xFF));
    bytes->push_back(static_cast<unsigned char>((value >> 16) & 0xFF));
    bytes->push_back(static_cast<unsigned char>((value >> 24) & 0xFF));
}

void AppendString(std::vector<unsigned char>* bytes, const char* value) {
    const std::string text(value);
    AppendU32(bytes, static_cast<std::uint32_t>(text.size()));
    bytes->insert(bytes->end(), text.begin(), text.end());
}

std::vector<unsigned char> Header(
    std::uint32_t panels,
    std::uint32_t meters,
    std::uint32_t research,
    std::uint32_t gates,
    std::uint32_t timed,
    std::uint32_t commands,
    std::uint32_t sovereign,
    std::uint32_t rewards = 0,
    std::uint32_t flags = 0) {
    std::vector<unsigned char> bytes = {'M', 'M', 'C', 'R'};
    AppendU32(&bytes, 2);
    AppendU32(&bytes, panels);
    AppendU32(&bytes, meters);
    AppendU32(&bytes, research);
    AppendU32(&bytes, gates);
    AppendU32(&bytes, timed);
    AppendU32(&bytes, commands);
    AppendU32(&bytes, sovereign);
    AppendU32(&bytes, rewards);
    AppendU32(&bytes, flags);
    return bytes;
}

void AppendPanel(
    std::vector<unsigned char>* bytes,
    const char* panel,
    const char parentDialog[5],
    const char childDialog[5],
    const char family[4],
    std::uint32_t command) {
    AppendString(bytes, panel);
    AppendU32(bytes, FourCC(parentDialog));
    AppendU32(bytes, FourCC(childDialog));
    const std::string familyText(family);
    std::uint32_t familyValue = 0;
    for (std::size_t index = 0; index < familyText.size() && index < 3; ++index) {
        familyValue |= static_cast<std::uint32_t>(
            static_cast<unsigned char>(familyText[index])) << (index * 8);
    }
    AppendU32(bytes, familyValue);
    AppendU32(bytes, command);
}

void AppendMeter(std::vector<unsigned char>* bytes) {
    AppendString(bytes, "brewing");
    AppendString(bytes, "reagents");
    AppendU32(bytes, FourCC("APV0"));
    AppendU32(bytes, 0x2A23);
    AppendU32(bytes, 0x2A24);
    AppendU32(bytes, 0x2A25);
}

void AppendMeterFor(
    std::vector<unsigned char>* bytes,
    const char* panel,
    const char* resource,
    const char attribute[5],
    std::uint32_t controlBase) {
    AppendString(bytes, panel);
    AppendString(bytes, resource);
    AppendU32(bytes, FourCC(attribute));
    AppendU32(bytes, controlBase);
    AppendU32(bytes, controlBase + 1);
    AppendU32(bytes, controlBase + 2);
}

void AppendResearch(
    std::vector<unsigned char>* bytes,
    const char* recipe,
    std::uint32_t action,
    std::uint32_t completionTemplate,
    std::uint32_t level,
    std::uint32_t price,
    std::uint32_t progress,
    std::uint32_t active,
    std::uint32_t icon,
    const char* completion,
    std::uint32_t descriptorTemplate = 0x139C) {
    AppendString(bytes, "brewing");
    AppendString(bytes, recipe);
    AppendU32(bytes, action);
    AppendU32(bytes, descriptorTemplate);
    AppendU32(bytes, completionTemplate);
    AppendU32(bytes, level);
    AppendU32(bytes, price);
    AppendU32(bytes, action + 1000);
    AppendU32(bytes, progress);
    AppendU32(bytes, active);
    AppendU32(bytes, icon);
    AppendString(bytes, completion);
}

void AppendTimedAction(
    std::vector<unsigned char>* bytes,
    const char* callback,
    std::uint32_t descriptorTemplate = 0x1140,
    std::uint32_t levelPriceTemplate = 0x113E,
    std::uint32_t requiredLevel = 3,
    std::uint32_t goldCost = 1500) {
    AppendString(bytes, "brewing");
    AppendString(bytes, "vigor-elixir");
    AppendU32(bytes, 0x2A10);
    AppendU32(bytes, descriptorTemplate);
    AppendU32(bytes, levelPriceTemplate);
    AppendU32(bytes, requiredLevel);
    AppendU32(bytes, goldCost);
    AppendString(bytes, "reagents");
    AppendU32(bytes, 1);
    AppendString(bytes, callback);
    AppendU32(bytes, 30000);
    AppendU32(bytes, 0x2A10 + 1000);
    AppendU32(bytes, 0x2A10 - 1000);
    AppendU32(bytes, 0x2009);
    AppendU32(bytes, 0x227A);
}

void AppendRageAction(
    std::vector<unsigned char>* bytes,
    const char* callback,
    std::uint32_t visualTemplate = 0x1132,
    std::uint32_t completionTemplate = 0x139C,
    std::uint32_t requiredLevel = 3) {
    AppendString(bytes, "brewing");
    AppendString(bytes, "arcane-infusion");
    AppendU32(bytes, 0x1132);
    AppendU32(bytes, visualTemplate);
    AppendU32(bytes, completionTemplate);
    AppendU32(bytes, requiredLevel);
    AppendString(bytes, "reagents");
    AppendU32(bytes, 10);
    AppendString(bytes, callback);
    AppendU32(bytes, 0x1132 + 1000);
    AppendU32(bytes, 0x1132 - 1000);
}

void AppendSovereignAction(
    std::vector<unsigned char>* bytes,
    std::uint32_t visualTemplate = 0x1133,
    std::uint32_t targetTemplate = 0x1132,
    const char stockTargetMode[5] = "Sp23",
    std::uint32_t requiredLevel = 3) {
    AppendString(bytes, "brewing");
    AppendString(bytes, "philosophers-stone");
    AppendU32(bytes, 0x1133);
    AppendU32(bytes, 0x2A21);
    AppendU32(bytes, visualTemplate);
    AppendU32(bytes, targetTemplate);
    AppendU32(bytes, FourCC(stockTargetMode));
    AppendU32(bytes, FourCC("Sp14"));
    AppendU32(bytes, FourCC("AlS1"));
    AppendU32(bytes, FourCC("ALS1"));
    AppendU32(bytes, 39);
    AppendU32(bytes, requiredLevel);
    AppendString(bytes, "reagents");
    AppendU32(bytes, 10);
    AppendU32(bytes, 0x1133 + 1000);
    AppendU32(bytes, 0x1133 - 1000);
}

void AppendRewardPanel(std::vector<unsigned char>* bytes) {
    AppendString(bytes, "reward-panel");
    AppendU32(bytes, FourCC("PR01"));
    AppendU32(bytes, FourCC("PC01"));
    AppendU32(bytes, 5001);
}

void AppendHostileFlag(std::vector<unsigned char>* bytes) {
    AppendString(bytes, "reward-panel");
    AppendString(bytes, "capture");
    AppendU32(bytes, FourCC("RF01"));
    AppendU32(bytes, FourCC("RF01"));
    AppendString(bytes, "Private_Reward_Flag");
    AppendU32(bytes, 38);
    AppendU32(bytes, 1);
    AppendU32(bytes, 0x00305A41u); // AZ0 with canonical trailing NUL
    AppendString(bytes, "No room remains");
}

std::vector<unsigned char> LegacyProfile() {
    std::vector<unsigned char> bytes = Header(1, 1, 2, 1, 1, 1, 1);
    AppendPanel(&bytes, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendMeter(&bytes);
    // Canonical key order is phoenix-phial, then weapon-oil.
    AppendResearch(
        &bytes, "phoenix-phial", 0x2A16, 0x13B3, 2, 750,
        0x2A17, 0x2A18, 0x2A16 + 500, "Phoenix Phial");
    AppendResearch(
        &bytes, "weapon-oil", 0x2A13, 0x139C, 1, 250,
        0x2A11, 0x2A12, 0, "Weapon Oil");

    AppendString(&bytes, "brewing");
    AppendU32(&bytes, 0x1F47);
    AppendU32(&bytes, 0x1F4F);
    AppendU32(&bytes, 2);
    AppendU32(&bytes, 1);
    AppendString(&bytes, "weapon-oil");
    AppendU32(&bytes, 2);
    AppendString(&bytes, "phoenix-phial");

    AppendTimedAction(&bytes, "Alchemist_DoInvigoratingElixer");
    AppendRageAction(&bytes, "Alchemist_Arcane_Infusion");

    AppendSovereignAction(&bytes);
    return bytes;
}

bool ExpectInvalid(
    const std::vector<unsigned char>& bytes,
    const char* expectedErrorPart) {
    MajestyStockControllers::Registry registry;
    std::string error;
    if (MajestyStockControllers::ParseRegistry(
            bytes.data(), bytes.size(), &registry, &error)) {
        std::fprintf(stderr, "Expected MMCR rejection.\n");
        return false;
    }
    if (error.find(expectedErrorPart) == std::string::npos) {
        std::fprintf(stderr, "Wrong MMCR rejection: expected '%s', got '%s'.\n",
            expectedErrorPart, error.c_str());
        return false;
    }
    return registry.panels.empty() && registry.meters.empty() &&
        registry.researchRows.empty() && registry.upgradeGates.empty() &&
        registry.timedRageActions.empty() &&
        registry.rageCommandActions.empty() &&
        registry.sovereignTargetActions.empty() &&
        registry.rewardPanels.empty() && registry.hostileMonsterFlags.empty() &&
        registry.occupantActionPanels.empty() &&
        registry.buildingOpenToggles.empty() && registry.liveAgentLists.empty();
}

}  // namespace

int main() {
    const std::vector<unsigned char> valid = LegacyProfile();
    std::uint32_t wireHash = 2166136261u;
    for (std::vector<unsigned char>::const_iterator byte = valid.begin();
         byte != valid.end(); ++byte) {
        wireHash = (wireHash ^ *byte) * 16777619u;
    }
    // The same fixture is emitted by Python's resolved-registry encoder.  This
    // guards field order and little-endian parity across the integration seam.
    if (valid.size() != 641 || wireHash != 0x269675CAu) {
        std::fprintf(stderr, "C++ MMCR fixture differs from Python canonical wire.\n");
        return 1;
    }
    MajestyStockControllers::Registry registry;
    std::string error;
    if (!MajestyStockControllers::ParseRegistry(
            valid.data(), valid.size(), &registry, &error)) {
        std::fprintf(stderr, "Valid MMCR rejected: %s\n", error.c_str());
        return 2;
    }
    if (registry.panels.size() != 1 || registry.meters.size() != 1 ||
        registry.researchRows.size() != 2 || registry.upgradeGates.size() != 1 ||
        registry.timedRageActions.size() != 1 ||
        registry.rageCommandActions.size() != 1 ||
        registry.sovereignTargetActions.size() != 1) {
        std::fprintf(stderr, "MMCR did not preserve all eight validated records.\n");
        return 3;
    }
    std::vector<unsigned char> reward = Header(0, 0, 0, 0, 0, 0, 0, 1, 1);
    AppendRewardPanel(&reward);
    AppendHostileFlag(&reward);
    MajestyStockControllers::Registry rewardRegistry;
    if (!MajestyStockControllers::ParseRegistry(
            reward.data(), reward.size(), &rewardRegistry, &error) ||
        rewardRegistry.rewardPanels.size() != 1 ||
        rewardRegistry.hostileMonsterFlags.size() != 1 ||
        rewardRegistry.hostileMonsterFlags[0].flagPrototypeName != "Private_Reward_Flag") {
        std::fprintf(stderr, "Generic reward MMCR rejected: %s\n", error.c_str());
        return 36;
    }
    if (registry.FindPanelByChildDialog(FourCC("CGBR")) == nullptr ||
        registry.FindPanelByParentDialog(FourCC("CGAL")) == nullptr ||
        registry.FindPanelByParentCommand(FourCC("CGAL"), 0x1F49) == nullptr ||
        registry.FindPanelByKey("brewing") == nullptr ||
        registry.FindMeter("brewing", "reagents") == nullptr ||
        registry.FindResearchByCommand(0x2A16) == nullptr ||
        registry.FindTimedRageByCommand(0x2A10) == nullptr ||
        registry.FindRageCommand("brewing", 0x1132) == nullptr ||
        registry.FindSovereignByPrivateMode(FourCC("AlS1")) == nullptr ||
        registry.FindPanelByKey("missing") != nullptr) {
        std::fprintf(stderr, "MMCR lookup model did not find exact records.\n");
        return 4;
    }

    const std::vector<unsigned char> empty = Header(0, 0, 0, 0, 0, 0, 0);
    if (!MajestyStockControllers::ParseRegistry(
            empty.data(), empty.size(), &registry, &error) ||
        !registry.panels.empty() || !registry.meters.empty() ||
        !registry.researchRows.empty() || !registry.upgradeGates.empty() ||
        !registry.timedRageActions.empty() ||
        !registry.rageCommandActions.empty() ||
        !registry.sovereignTargetActions.empty()) {
        std::fprintf(stderr, "Canonical empty MMCR rejected: %s\n", error.c_str());
        return 21;
    }

    for (std::size_t size = 0; size < valid.size(); ++size) {
        MajestyStockControllers::Registry truncated;
        std::string truncatedError;
        if (MajestyStockControllers::ParseRegistry(
                valid.data(), size, &truncated, &truncatedError)) {
            std::fprintf(stderr, "MMCR truncation at %u bytes was accepted.\n",
                static_cast<unsigned int>(size));
            return 5;
        }
    }
    std::vector<unsigned char> trailing = valid;
    trailing.push_back(0);
    if (!ExpectInvalid(trailing, "trailing")) return 6;
    std::vector<unsigned char> wrongMagic = valid;
    wrongMagic[0] = 'X';
    if (!ExpectInvalid(wrongMagic, "magic")) return 7;
    std::vector<unsigned char> wrongVersion = valid;
    wrongVersion[4] = 1;
    if (!ExpectInvalid(wrongVersion, "version")) return 8;
    std::vector<unsigned char> tooMany = Header(257, 0, 0, 0, 0, 0, 0);
    if (!ExpectInvalid(tooMany, "count")) return 9;

    std::vector<unsigned char> badIdentifier = valid;
    // Header, then panel-key length; replace the first panel-key byte.
    badIdentifier[48] = '/';
    if (!ExpectInvalid(badIdentifier, "panel")) return 10;

    std::vector<unsigned char> canonicalPanels = Header(2, 0, 0, 0, 0, 0, 0);
    AppendPanel(&canonicalPanels, "alpha", "PA01", "PX01", "AAA", 0x4001);
    AppendPanel(&canonicalPanels, "beta", "PB01", "PX02", "BBB", 0x4002);
    if (!MajestyStockControllers::ParseRegistry(
            canonicalPanels.data(), canonicalPanels.size(), &registry, &error) ||
        registry.panels.size() != 2) {
        std::fprintf(stderr, "Canonical multi-panel MMCR rejected: %s\n", error.c_str());
        return 11;
    }
    std::vector<unsigned char> reversedPanels = Header(2, 0, 0, 0, 0, 0, 0);
    AppendPanel(&reversedPanels, "beta", "PB01", "PX02", "BBB", 0x4002);
    AppendPanel(&reversedPanels, "alpha", "PA01", "PX01", "AAA", 0x4001);
    if (!ExpectInvalid(reversedPanels, "noncanonical")) return 12;

    std::vector<unsigned char> duplicateFamily = Header(2, 0, 0, 0, 0, 0, 0);
    AppendPanel(&duplicateFamily, "alpha", "PA01", "PX01", "AAA", 0x4001);
    AppendPanel(&duplicateFamily, "beta", "PB01", "PX02", "AAA", 0x4002);
    if (!ExpectInvalid(duplicateFamily, "identity")) return 13;

    std::vector<unsigned char> overlappingFamily = Header(2, 0, 0, 0, 0, 0, 0);
    AppendPanel(&overlappingFamily, "alpha", "PA01", "PX01", "A", 0x4001);
    AppendPanel(&overlappingFamily, "beta", "PB01", "PX02", "AB", 0x4002);
    if (!ExpectInvalid(overlappingFamily, "prefixes overlap")) return 22;

    std::vector<unsigned char> duplicateMeterAttribute =
        Header(2, 2, 0, 0, 0, 0, 0);
    AppendPanel(
        &duplicateMeterAttribute, "alpha", "PA01", "PX01", "AAA", 0x4001);
    AppendPanel(
        &duplicateMeterAttribute, "beta", "PB01", "PX02", "BBB", 0x4002);
    AppendMeterFor(
        &duplicateMeterAttribute, "alpha", "first", "RS01", 0x5000);
    AppendMeterFor(
        &duplicateMeterAttribute, "beta", "second", "RS01", 0x6000);
    if (!ExpectInvalid(duplicateMeterAttribute, "resource meter references")) {
        return 24;
    }

    std::vector<unsigned char> collidingPrivateMode = valid;
    const unsigned char privateMode[] = {'A', 'l', 'S', '1'};
    std::vector<unsigned char>::iterator privateModePosition = std::search(
        collidingPrivateMode.begin(), collidingPrivateMode.end(),
        privateMode, privateMode + sizeof(privateMode));
    if (privateModePosition == collidingPrivateMode.end()) return 14;
    const unsigned char stockExecutorMode[] = {'S', 'p', '1', '4'};
    std::copy(
        stockExecutorMode,
        stockExecutorMode + sizeof(stockExecutorMode),
        privateModePosition);
    if (!ExpectInvalid(collidingPrivateMode, "sovereign action")) {
        return 15;
    }

    std::vector<unsigned char> reservedStockMode = valid;
    privateModePosition = std::search(
        reservedStockMode.begin(), reservedStockMode.end(),
        privateMode, privateMode + sizeof(privateMode));
    if (privateModePosition == reservedStockMode.end()) return 19;
    const unsigned char otherStockMode[] = {'S', 'p', '3', '7'};
    std::copy(
        otherStockMode,
        otherStockMode + sizeof(otherStockMode),
        privateModePosition);
    if (!ExpectInvalid(reservedStockMode, "sovereign action")) return 20;

    std::vector<unsigned char> unprovedExecutor = valid;
    const unsigned char executorMode[] = {'S', 'p', '1', '4'};
    std::vector<unsigned char>::iterator executorPosition = std::search(
        unprovedExecutor.begin(), unprovedExecutor.end(),
        executorMode, executorMode + sizeof(executorMode));
    if (executorPosition == unprovedExecutor.end()) return 16;
    executorPosition[3] = '5';
    if (!ExpectInvalid(unprovedExecutor, "sovereign action")) return 17;

    std::vector<unsigned char> callbackCollision =
        Header(1, 1, 0, 0, 1, 1, 0);
    AppendPanel(
        &callbackCollision, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendMeter(&callbackCollision);
    AppendTimedAction(&callbackCollision, "ApplyThing");
    AppendRageAction(&callbackCollision, "applything");
    if (!ExpectInvalid(callbackCollision, "references are invalid")) return 18;

    for (const std::uint32_t stockAp99Key : {0x1388u, 0x139Cu, 0x13EBu}) {
        std::vector<unsigned char> stockAp99Collision =
            Header(1, 0, 1, 0, 0, 0, 0);
        AppendPanel(
            &stockAp99Collision, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
        AppendResearch(
            &stockAp99Collision, "stock-collision", stockAp99Key,
            0x139C, 1, 250, 0x5000, 0x5001, 0x5002, "Collision");
        if (!ExpectInvalid(stockAp99Collision, "stock-owned")) return 22;
    }
    std::vector<unsigned char> firstPrivateAp99 =
        Header(1, 0, 1, 0, 0, 0, 0);
    AppendPanel(
        &firstPrivateAp99, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendResearch(
        &firstPrivateAp99, "first-private", 0x13EC,
        0x139C, 1, 250, 0x5000, 0x5001, 0x5002, "Private");
    if (!MajestyStockControllers::ParseRegistry(
            firstPrivateAp99.data(), firstPrivateAp99.size(),
            &registry, &error)) {
        std::fprintf(
            stderr,
            "First control after stock AP99 namespace was rejected: %s\n",
            error.c_str());
        return 23;
    }

    std::vector<unsigned char> provenAp99Templates =
        Header(1, 0, 1, 0, 0, 0, 0);
    AppendPanel(
        &provenAp99Templates, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendResearch(
        &provenAp99Templates, "proven-templates", 0x13EC,
        0x13CA, 1, 250, 0x5000, 0x5001, 0x5002, "Proven", 0x1388);
    if (!MajestyStockControllers::ParseRegistry(
            provenAp99Templates.data(), provenAp99Templates.size(),
            &registry, &error)) {
        std::fprintf(stderr, "Proven AP99 template endpoints rejected: %s\n",
            error.c_str());
        return 25;
    }

    std::vector<unsigned char> missingAp99Descriptor =
        Header(1, 0, 1, 0, 0, 0, 0);
    AppendPanel(
        &missingAp99Descriptor, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendResearch(
        &missingAp99Descriptor, "gap-template", 0x13EC,
        0x139C, 1, 250, 0x5000, 0x5001, 0x5002, "Gap", 0x138E);
    if (!ExpectInvalid(missingAp99Descriptor, "AP99 research row")) return 26;

    std::vector<unsigned char> missingAp99Completion =
        Header(1, 0, 1, 0, 0, 0, 0);
    AppendPanel(
        &missingAp99Completion, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendResearch(
        &missingAp99Completion, "missing-completion", 0x13EC,
        0x13EC, 1, 250, 0x5000, 0x5001, 0x5002, "Missing");
    if (!ExpectInvalid(missingAp99Completion, "AP99 research row")) return 27;

    std::vector<unsigned char> badTimedPair =
        Header(1, 1, 0, 0, 1, 0, 0);
    AppendPanel(&badTimedPair, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendMeter(&badTimedPair);
    AppendTimedAction(
        &badTimedPair, "TimedPair", 0x1132, 0x113E, 3, 1500);
    if (!ExpectInvalid(badTimedPair, "timed Rage action")) return 28;

    std::vector<unsigned char> badTimedMetadata =
        Header(1, 1, 0, 0, 1, 0, 0);
    AppendPanel(
        &badTimedMetadata, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendMeter(&badTimedMetadata);
    AppendTimedAction(
        &badTimedMetadata, "TimedMetadata", 0x1140, 0x113E, 2, 1499);
    if (!ExpectInvalid(badTimedMetadata, "timed Rage action")) return 29;

    std::vector<unsigned char> badRageVisual =
        Header(1, 1, 0, 0, 0, 1, 0);
    AppendPanel(&badRageVisual, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendMeter(&badRageVisual);
    AppendRageAction(&badRageVisual, "RageVisual", 0x1133, 0x139C, 3);
    if (!ExpectInvalid(badRageVisual, "Rage command action")) return 30;

    std::vector<unsigned char> badRageCompletion =
        Header(1, 1, 0, 0, 0, 1, 0);
    AppendPanel(
        &badRageCompletion, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendMeter(&badRageCompletion);
    AppendRageAction(&badRageCompletion, "RageCompletion", 0x1132, 0x13EC, 3);
    if (!ExpectInvalid(badRageCompletion, "Rage command action")) return 31;

    std::vector<unsigned char> badRageLevel =
        Header(1, 1, 0, 0, 0, 1, 0);
    AppendPanel(&badRageLevel, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendMeter(&badRageLevel);
    AppendRageAction(&badRageLevel, "RageLevel", 0x1132, 0x139C, 2);
    if (!ExpectInvalid(badRageLevel, "Rage command action")) return 32;

    std::vector<unsigned char> badSovereignVisual =
        Header(1, 1, 0, 0, 0, 0, 1);
    AppendPanel(
        &badSovereignVisual, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendMeter(&badSovereignVisual);
    AppendSovereignAction(&badSovereignVisual, 0x1132, 0x1132, "Sp23", 3);
    if (!ExpectInvalid(badSovereignVisual, "sovereign action")) return 33;

    std::vector<unsigned char> badSovereignTarget =
        Header(1, 1, 0, 0, 0, 0, 1);
    AppendPanel(
        &badSovereignTarget, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendMeter(&badSovereignTarget);
    AppendSovereignAction(&badSovereignTarget, 0x1133, 0x1133, "Sp23", 3);
    if (!ExpectInvalid(badSovereignTarget, "sovereign action")) return 34;

    std::vector<unsigned char> badSovereignMetadata =
        Header(1, 1, 0, 0, 0, 0, 1);
    AppendPanel(
        &badSovereignMetadata, "brewing", "CGAL", "CGBR", "ALB", 0x1F49);
    AppendMeter(&badSovereignMetadata);
    AppendSovereignAction(
        &badSovereignMetadata, 0x1133, 0x1132, "Sp24", 2);
    if (!ExpectInvalid(badSovereignMetadata, "sovereign action")) return 35;

    auto occupants = Header(0, 0, 0, 0, 0, 0, 0);
    occupants[4] = 3;
    AppendU32(&occupants, 1);
    AppendString(&occupants, "stable");
    AppendU32(&occupants, FourCC("B001"));
    AppendU32(&occupants, FourCC("P001"));
    AppendU32(&occupants, 0x4101);
    const auto commandOffset = occupants.size();
    AppendU32(&occupants, 0x10000);
    AppendString(&occupants, "Stable_Cost");
    AppendString(&occupants, "Stable_Action");
    AppendU32(&occupants, FourCC("AP10"));
    if (!MajestyStockControllers::ParseRegistry(occupants.data(), occupants.size(), &registry, &error) ||
        registry.occupantActionPanels.size() != 1 ||
        registry.FindOccupantPanelByCommand(0x10000) == nullptr ||
        registry.FindOccupantPanelByCommand(21) != nullptr) return 36;
    auto ap08Occupants = occupants;
    const std::uint32_t ap08 = FourCC("AP08");
    for (std::size_t index = 0; index < 4; ++index) {
        ap08Occupants[ap08Occupants.size() - 4 + index] =
            static_cast<unsigned char>((ap08 >> (index * 8)) & 0xFF);
    }
    if (!MajestyStockControllers::ParseRegistry(
            ap08Occupants.data(), ap08Occupants.size(), &registry, &error) ||
        registry.occupantActionPanels.size() != 1 ||
        registry.occupantActionPanels[0].parentControllerBase != ap08) return 45;
    auto ap31Occupants = occupants;
    const std::uint32_t ap31 = FourCC("AP31");
    for (std::size_t index = 0; index < 4; ++index) {
        ap31Occupants[ap31Occupants.size() - 4 + index] =
            static_cast<unsigned char>((ap31 >> (index * 8)) & 0xFF);
    }
    if (!MajestyStockControllers::ParseRegistry(
            ap31Occupants.data(), ap31Occupants.size(), &registry, &error) ||
        registry.occupantActionPanels.size() != 1 ||
        registry.occupantActionPanels[0].parentControllerBase != ap31) return 55;
    auto unknownParent = occupants;
    const std::uint32_t ap03 = FourCC("AP03");
    for (std::size_t index = 0; index < 4; ++index) {
        unknownParent[unknownParent.size() - 4 + index] =
            static_cast<unsigned char>((ap03 >> (index * 8)) & 0xFF);
    }
    if (!ExpectInvalid(unknownParent, "occupant panel")) return 56;
    for (std::size_t size = 0; size < occupants.size(); ++size) {
        if (MajestyStockControllers::ParseRegistry(occupants.data(), size, &registry, &error)) return 37;
    }
    occupants[commandOffset] = 21;
    if (!ExpectInvalid(occupants, "occupant panel")) return 38;

    auto toggles = Header(0, 0, 0, 0, 0, 0, 0);
    toggles[4] = 4;
    AppendU32(&toggles, 0);
    AppendU32(&toggles, 1);
    AppendString(&toggles, "rentals");
    AppendU32(&toggles, FourCC("Z001"));
    AppendU32(&toggles, 0x5D01);
    AppendU32(&toggles, 0x5D02);
    AppendU32(&toggles, FourCC("AP08"));
    if (!MajestyStockControllers::ParseRegistry(
            toggles.data(), toggles.size(), &registry, &error) ||
        registry.buildingOpenToggles.size() != 1 ||
        registry.buildingOpenToggles[0].parentControllerBase != FourCC("AP08") ||
        registry.FindBuildingOpenToggleByParent(FourCC("Z001")) == nullptr) {
        std::fprintf(stderr, "Generic building-toggle MMCR rejected: %s\n", error.c_str());
        return 39;
    }
    for (std::size_t size = 0; size < toggles.size(); ++size) {
        if (MajestyStockControllers::ParseRegistry(
                toggles.data(), size, &registry, &error)) return 40;
    }

    auto quests = Header(0, 0, 0, 0, 0, 0, 0);
    quests[4] = 15;
    AppendU32(&quests, 0);  // occupant panels
    AppendU32(&quests, 0);  // building toggles
    AppendU32(&quests, 1);  // live-agent lists
    AppendString(&quests, "agent-list");
    AppendU32(&quests, FourCC("AGP1"));
    AppendU32(&quests, FourCC("QBP1"));
    AppendU32(&quests, 0x7101);
    AppendU32(&quests, 0x20000);  // native bottom action
    const char* questLeadingCallbacks[] = {
        "QB_Count", "QB_Agent_Id", "QB_Revision",
    };
    for (std::size_t index = 0;
         index < sizeof(questLeadingCallbacks) / sizeof(questLeadingCallbacks[0]); ++index) {
        AppendString(&quests, questLeadingCallbacks[index]);
    }
    AppendU32(&quests, 0);  // use each live agent's stock name
    AppendU32(&quests, 0);  // variant-selected row text
    AppendU32(&quests, 1);  // optional row variants present
    AppendString(&quests, "QB_Variant");
    AppendU32(&quests, 2);
    AppendU32(&quests, 0x68000001u);
    AppendU32(&quests, 0x68000002u);
    AppendU32(&quests, 0x68000003u);
    AppendU32(&quests, 0x68000004u);
    AppendU32(&quests, 1);  // optional value present
    AppendString(&quests, "QB_Reward");
    AppendU32(&quests, 0x68000005u);  // value suffix text
    const char* questCallbacks[] = {
        "QB_RefreshCost", "QB_Refresh",
    };
    for (std::size_t index = 0;
         index < sizeof(questCallbacks) / sizeof(questCallbacks[0]); ++index) {
        AppendString(&quests, questCallbacks[index]);
    }
    AppendU32(&quests, FourCC("AP08"));
    AppendU32(&quests, 1);  // remain on this child after a successful action
    AppendU32(&quests, 0);  // do not focus the selected row's world target
    AppendU32(&quests, 1);  // quote and execute the action against its parent
    if (!MajestyStockControllers::ParseRegistry(
            quests.data(), quests.size(), &registry, &error) ||
        registry.liveAgentLists.size() != 1 ||
        !registry.liveAgentLists[0].hasRowVariants ||
        registry.liveAgentLists[0].rowVariants.size() != 2 ||
        !registry.liveAgentLists[0].stayOnPanelAfterAction ||
        registry.liveAgentLists[0].focusSelectedRowOnClick ||
        !registry.liveAgentLists[0].actionUsesParent ||
        registry.FindLiveAgentListByChild(FourCC("QBP1")) == nullptr ||
        registry.FindLiveAgentListByParent(FourCC("AGP1")) == nullptr ||
        registry.FindLiveAgentListByCommand(0x20000) == nullptr) {
        std::fprintf(stderr, "Generic live-agent-list MMCR rejected: %s\n", error.c_str());
        return 41;
    }
    auto invalidStayPolicy = quests;
    auto dataRecords = quests;
    dataRecords[4] = 16;
    AppendU32(&dataRecords, 1);
    if (!MajestyStockControllers::ParseRegistry(dataRecords.data(), dataRecords.size(), &registry, &error) ||
        !registry.liveAgentLists[0].dataRecordRows) return 57;
    dataRecords[dataRecords.size()-8] = 0; // invalid selected-row action scope
    if (!ExpectInvalid(dataRecords, "data-record list")) return 58;
    invalidStayPolicy[invalidStayPolicy.size() - 12] = 2;
    if (!ExpectInvalid(invalidStayPolicy, "live-agent-list record")) return 52;
    auto invalidFocusPolicy = quests;
    invalidFocusPolicy[invalidFocusPolicy.size() - 8] = 2;
    if (!ExpectInvalid(invalidFocusPolicy, "live-agent-list record")) return 53;
    auto invalidActionScope = quests;
    invalidActionScope[invalidActionScope.size() - 4] = 2;
    if (!ExpectInvalid(invalidActionScope, "live-agent-list record")) return 55;
    auto v14Quests = quests;
    v14Quests[4] = 14;
    v14Quests.resize(v14Quests.size() - 4);
    if (!MajestyStockControllers::ParseRegistry(
            v14Quests.data(), v14Quests.size(), &registry, &error) ||
        registry.liveAgentLists.size() != 1 ||
        registry.liveAgentLists[0].actionUsesParent) {
        std::fprintf(stderr, "MMCR v14 compatibility rejected: %s\n", error.c_str());
        return 56;
    }
    std::vector<unsigned char> obsoleteQuests = quests;
    obsoleteQuests[4] = 13;
    if (!ExpectInvalid(obsoleteQuests, "v13 live-agent lists")) return 54;
    obsoleteQuests = quests;
    obsoleteQuests[4] = 12;
    if (!ExpectInvalid(obsoleteQuests, "v12 live-agent lists")) return 51;
    obsoleteQuests = quests;
    obsoleteQuests[4] = 11;
    if (!ExpectInvalid(obsoleteQuests, "v11 live-agent lists")) return 50;
    obsoleteQuests = quests;
    obsoleteQuests[4] = 10;
    if (!ExpectInvalid(obsoleteQuests, "v10 one-row quest lists")) return 48;
    obsoleteQuests = quests;
    obsoleteQuests[4] = 9;
    if (!ExpectInvalid(obsoleteQuests, "v9 quest boards")) return 49;
    obsoleteQuests = quests;
    obsoleteQuests[4] = 5;
    if (!ExpectInvalid(obsoleteQuests, "v5 fixed-row")) return 43;
    obsoleteQuests = quests;
    obsoleteQuests[4] = 6;
    if (!ExpectInvalid(obsoleteQuests, "v6 quest rows")) return 44;
    obsoleteQuests = quests;
    obsoleteQuests[4] = 7;
    if (!ExpectInvalid(obsoleteQuests, "v7 quest rows")) return 46;
    obsoleteQuests = quests;
    obsoleteQuests[4] = 8;
    if (!ExpectInvalid(obsoleteQuests, "v8 quest rows")) return 47;
    for (std::size_t size = 0; size < quests.size(); ++size) {
        if (MajestyStockControllers::ParseRegistry(
                quests.data(), size, &registry, &error)) return 42;
    }
    std::puts("Stock controller registry parser tests passed.");
    return 0;
}
