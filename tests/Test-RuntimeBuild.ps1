$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$buildScript = Join-Path $repoRoot "scripts\Build-Runtime.ps1"
$output = Join-Path $repoRoot "artifacts\runtime-test"

function Assert-X86Pe {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][bool]$ExpectDll
    )
    [byte[]]$bytes = [IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 256 -or $bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) {
        throw "$Path is not a PE image."
    }
    $peOffset = [BitConverter]::ToInt32($bytes, 0x3C)
    $machine = [BitConverter]::ToUInt16($bytes, $peOffset + 4)
    $characteristics = [BitConverter]::ToUInt16($bytes, $peOffset + 22)
    if ($machine -ne 0x014C) { throw "$Path is not x86 (machine 0x$($machine.ToString('X4')))." }
    $isDll = ($characteristics -band 0x2000) -ne 0
    if ($isDll -ne $ExpectDll) { throw "$Path DLL characteristic does not match expectation." }
}

function Get-CppGuardBlocks {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Condition
    )
    $needle = "if ($Condition) {"
    $cursor = 0
    $blocks = New-Object System.Collections.Generic.List[string]
    while ($cursor -lt $Source.Length) {
        $start = $Source.IndexOf($needle, $cursor, [StringComparison]::Ordinal)
        if ($start -lt 0) { break }
        $brace = $Source.IndexOf('{', $start)
        $depth = 0
        $end = -1
        for ($index = $brace; $index -lt $Source.Length; $index++) {
            if ($Source[$index] -eq '{') { $depth++ }
            elseif ($Source[$index] -eq '}') {
                $depth--
                if ($depth -eq 0) {
                    $end = $index
                    break
                }
            }
        }
        if ($end -lt 0) { throw "Unterminated C++ capability guard: $Condition" }
        $blocks.Add($Source.Substring($start, $end - $start + 1))
        $cursor = $end + 1
    }
    return $blocks
}

try {
    & $buildScript -OutputRoot $output
    Assert-X86Pe (Join-Path $output "MajestyBuildingRuntime.dll") $true
    Assert-X86Pe (Join-Path $output "MajestyBuildingRuntimeLauncher.exe") $false
    $runtimeSource = Get-Content -Raw (Join-Path $repoRoot "runtime\MajestyModManagerRuntime.cpp")
    $controllerLifecycleSource = Get-Content -Raw (Join-Path $repoRoot "runtime\ControllerLifecycleRegistry.cpp")
    $controllerLifecycleHeader = Get-Content -Raw (Join-Path $repoRoot "runtime\ControllerLifecycleRegistry.h")
    $intentRegistrySource = Get-Content -Raw (Join-Path $repoRoot "runtime\IntentTextRegistry.cpp")
    $intentRegistryHeader = Get-Content -Raw (Join-Path $repoRoot "runtime\IntentTextRegistry.h")
    $capabilitySource = Get-Content -Raw (Join-Path $repoRoot "runtime\RuntimeCapabilityManifest.cpp")
    $capabilityHeader = Get-Content -Raw (Join-Path $repoRoot "runtime\RuntimeCapabilityManifest.h")
    $freestyleSource = Get-Content -Raw (Join-Path $repoRoot "runtime\FreestyleCamRuntime.cpp")
    $launcherSource = Get-Content -Raw (Join-Path $repoRoot "runtime\MajestyBuildingRuntimeLauncher.cpp")
    $probeSource = Get-Content -Raw (Join-Path $repoRoot "scripts\Launch-RuntimeProbe.ps1")
    $crashProbeSource = Get-Content -Raw (Join-Path $repoRoot "scripts\Launch-CrashCaptureProbe.ps1")
    foreach ($contract in @(
        "QuoteCommandLineArgument",
        "[game arguments...]",
        "for (int index = 3; index < argc; ++index)",
        "MAJESTY_MOD_MANAGER_CAPABILITIES",
        "MAJESTY_MOD_MANAGER_PROFILE_LOCK_HANDLE",
        "MAJESTY_BUILDING_RUNTIME_READY_EVENT",
        "ReadInheritedProfileLock",
        "GetHandleInformation",
        "FILE_TYPE_DISK",
        "WaitForMultipleObjects",
        "ResumeThread(process.hThread)",
        "WaitForSingleObject(process.hProcess, INFINITE)",
        "CloseProfileLock(&profileLock)"
    )) {
        if (-not $launcherSource.Contains($contract)) {
            throw "Runtime launcher argument-forwarding contract is missing: $contract"
        }
    }
    if (-not $probeSource.Contains('[string[]]$GameArguments = @()') -or
        -not $probeSource.Contains('$launcher $game $dll @GameArguments')) {
        throw "Runtime probe does not forward optional Majesty command-line arguments."
    }
    foreach ($contract in @(
        'Windows Error Reporting\LocalDumps\MajestyHD.exe',
        '$dumpKey.SetValue("DumpType", 2',
        '$dumpKey.SetValue("DumpFolder", $session',
        'autosave-before.GMP',
        'autosave-after.GMP',
        'gpl.log',
        'gpl-session.log',
        'majestyhd_crash_*.mdmp',
        '[string[]]$GameArguments = @("-debugout")'
    )) {
        if (-not $crashProbeSource.Contains($contract)) {
            throw "Crash-capture probe contract is missing: $contract"
        }
    }
    [void][scriptblock]::Create($crashProbeSource)
    foreach ($contract in @(
        "RegisterManagedVtable",
        "ManagedControllerDestructor",
        "InterlockedCompareExchange",
        "registration->stockDestructor(controller, deleteFlags)",
        "HeapAlloc",
        "InterlockedExchangePointer"
    )) {
        if (-not $controllerLifecycleSource.Contains($contract) -and
            -not $controllerLifecycleHeader.Contains($contract)) {
            throw "Generic controller lifecycle contract is missing: $contract"
        }
    }
    foreach ($contract in @(
        '"public-1.5.2.24"',
        '"beta2-1.5.2.28"',
        "SelectMajestyBuildProfile",
        "ValidateMajestyBuildProfile",
        "InstallPrivateEnchantmentRows",
        "HeroEnchantmentsSwitchHook",
        "PrivateEnchantmentRowStringHook",
        "resolveIntentTextRva",
        "expectedResolveIntentTextEntry[6]",
        "intentTextTableProviderRva",
        "resolveIntentTextResumeRva",
        "LoadPrivateIntentRegistry",
        "ValidatePrivateIntentTextProfile",
        "ResolveManagerIntentText",
        "InstallPrivateIntentTextResolver",
        "StopUnsafeManagerRuntimeLaunch",
        "RequireManagerRuntimeInstall",
        "SignalManagerRuntimeReady",
        "LoadRuntimeCapabilityManifest",
        "MAJESTY_MOD_MANAGER_CAPABILITIES",
        "MAJESTY_BUILDING_RUNTIME_READY_EVENT",
        "MAJESTY_MOD_MANAGER_INTENT_REGISTRY",
        "manager-owned activity-text resolver",
        "g_stockIntentTextResolver(intentId, destination)",
        "g_privateIntentStringAssign(destination, privateText)",
        "struct MajestyStringView",
        'static_assert(sizeof(MajestyStringView) == 12',
        "AP22 Healing Potion count dispatch",
        "vtable[0x5C / sizeof(void*)]",
        "g_paralyticOilEnchantmentString",
        "g_transmutationOilEnchantmentString",
        "g_poisonedWeaponEnchantmentString",
        "Paralytic Oil - brief stun on weapon hit",
        "Transmutation Oil - +5 gold on weapon hit",
        "Poisoned Weapon - poison on weapon hit",
        "nameRegistryCompletionRva",
        "expectedNameRegistryCompletion[7]",
        "stockOperatorNewRva",
        "nameGeneratorFactoryRva",
        "nameGeneratorConstructRva",
        "nameRegistryFindOrInsertRva",
        "sovereignSpellClickRva",
        "expectedSovereignSpellClickEntry[9]",
        "sovereignTargetManagerRva",
        "expectedSovereignTargetManagerEntry[7]",
        "sovereignTargetCancelRva",
        "expectedSovereignTargetCancelEntry[11]",
        "sovereignCursorTransitionRva",
        "expectedSovereignCursorTransition[23]",
        "0x000AE420",
        "0x000AED10",
        "0x0005E5D0",
        "0x0005F600",
        "0x0005E9D0",
        "0x0005FA00",
        "0x0005EE25",
        "0x0005FE55",
        "beginSovereignTarget(privateControlId)",
        "kPhilosophersStoneCursorOrdinal = 39",
        "kStockVinesControlId = 0x00001132",
        "kStockVinesMode = 0x33327053",
        "SovereignCursorTransitionHook",
        "kStockUnaffordableGoldCost = 0x3FFFFFFF",
        "Stock temple spells still submit their current target packet",
        "Majesty's stock unaffordable-spell route",
        "UpdateSovereignBrewingGate",
        "g_sovereignCursorTransitionResume",
        "cmp dword ptr [edi], 33327053h",
        "mov eax, 39",
        "kReagentStockAttributeId = 0x30565041",
        "kReagentMeterCountControlId = 0x00002A24",
        "kReagentMeterCountBindingId = 0x00002A25",
        "SetControllerControlInteger",
        "Literal AP22 Healing Potion count dispatch",
        "vtable[0x5C / sizeof(void*)]",
        "descriptor[0] = kLaboratoryBuildingClassId;",
        "descriptor[3] = laboratoryLevelMet ? 0u : 3u;",
        "kStockLastNameGeneratorId = 0x37314D4E",
        "kAlchemistNameGeneratorId = 0x38314D4E",
        "kAlchemistGivenNamesId = 0x39364E48",
        "kAlchemistEndingsId = 0x30374E48",
        "kAlchemistThirdNamePartId = 0x31374E48",
        "kAlchemistFourthNamePartId = 0x32374E48",
        "kPhantomNameGeneratorId = 0x39314D4E",
        "kPhantomGivenNamesId = 0x33374E48",
        "kPhantomEndingsId = 0x34374E48",
        "kPhantomThirdNamePartId = 0x35374E48",
        "kPhantomFourthNamePartId = 0x36374E48",
        "RegisterRequestedPrivateNameGenerators",
        "RegisterPrivateStockNameGenerator",
        "NameRegistryCompletionHook",
        "InstallPrivateNameGenerators",
        "Registered private %s through Majesty's stock name-generator registry lifecycle.",
        "kParalyticOilOverlayId = 0x316F4C41",
        "kTransmutationOilOverlayId = 0x326F4C41",
        "kPoisonedWeaponOverlayId = 0x336F4C41",
        "kSpeedTonicOverlayId = 0x31305258",
        "AP78 Enchantments stock switch",
        "AP78 Speed Tonic row string assignment",
        "Runtime refused unknown Majesty build timestamp",
        "secondaryControllerResultRva",
        "expectedResultSite[6]",
        "test eax, eax",
        "LogSuppressedNullSecondaryController",
        "kBrewingParentCommandId = 0x00001F49",
        "kBuildingUpgradeControlId = 0x00001F47",
        "kBuildingUpgradePriceControlId = 0x00001F4F",
        "kInvigoratingElixerIconControlId",
        "kWeaponOilResearchPriceControlId",
        "kWeaponOilCompletionAttributeId = 0x2A425041",
        "kPhoenixPhialCompletionAttributeId = 0x29425041",
        "LaboratoryUpgradeResearchComplete",
        "ApplyLaboratoryUpgradeResearchGate",
        "LaboratoryControllerEvent",
        "kAp10VtableEntries = 17",
        "LaboratoryControllerControl",
        "Ignored repeated Brewing command with AP10's stock no-action result.",
        "Armed CGAL secondary mapping from AP10's stock Brewing command.",
        "Creation entry captured CGAL without arming a secondary request.",
        "dialogFactoryRva",
        "customGuildFallbackRva",
        "sharedGuildControllerRva",
        "BuildCustomGuildFactoryPatch",
        "ValidateCustomGuildFactoryFallback",
        "InstallCustomGuildFactoryFallback",
        "in-memory stock CG-prefix guild-controller fallback",
        "DialogFactoryTraceHook",
        "dialogCreationRva",
        "expectedCreationEntry[7]",
        "DialogCreationHook",
        "Dialog creation entry: id=0x%08X context=0x%08X owner=0x%08X arg4=0x%08X",
        "before setup-object construction",
        "g_customBrewingActive",
        "Redirected custom Brewing Back request from AP10 to CGAL",
        "removeDialogRva",
        "Captured the custom Brewing controller and installed its scoped vtable",
        "WM_RBUTTONDOWN",
        "Majesty's native dialog-removal API",
        "xor eax, eax",
        "kCgalDialogId = 0x4C414743",
        "kCgbrDialogId = 0x52424743",
        "kAp69DialogId = 0x39365041",
        "Translated armed CGAL secondary request to AP69",
        "with its Laboratory context",
        "kRageOfKrolmCommandId = 1",
        "kInvigoratingElixerGoldCost = 1500",
        "kInvigoratingElixerReagentCost = 1",
        "kPlayerGoldDataId = 0x00505041",
        "StockCurrentPlayerGold()",
        "vtable[0x20 / sizeof(void*)]",
        "Stock AP24 affordability gate rejected Invigorating Elixer",
        "getPlayerAgentRva",
        "readPackedAttributeRva",
        "kRageOfKrolmCountAttributeId = 0x07425041",
        "StockRageOfKrolmCount()",
        "Ignored Invigorating Elixer while stock Rage owns the Palace count.",
        "getCommandMetadataRva",
        "rageCommandDispatchRva",
        "ragePrivateBranchRva",
        "rageGplConstructionResumeRva",
        "Alchemist_DoInvigoratingElixer",
        "Alchemist_Arcane_Infusion",
        "getCommandMetadata(context, &metadata)",
        "metadata.first",
        "metadata.second",
        "kInvigoratingElixerDurationMs = 30000",
        "simulationClockRva",
        "gameUpdateCallRva",
        "gameUpdateRva",
        "expectedGameUpdateCall[5]",
        "0xE8, 0xDE, 0x13, 0x00, 0x00",
        "GameUpdateRefreshBridge",
        "g_stockGameUpdate(gameState)",
        "InstallGameUpdateRefreshBridge",
        "stock state-3 update dispatch",
        "kInvigoratingElixerProgressControlId = 0x00002009",
        "kInvigoratingElixerActiveDisplayControlId = 0x0000227A",
        "kInvigoratingElixerControlId = 0x00002A10",
        "resolveSpellDescriptorRva",
        "ResolvePrivateInvigoratingDescriptor",
        "kStockFervusHealingControlId = 0x00001140",
        "refreshSingleSpellRowRva",
        "RefreshInvigoratingElixer",
        "kStockPetrifyControlId = 0x0000113E",
        "stockPetrify[3] != 3",
        "g_invigoratingSpellDescriptor[4] = stockPetrify[4]",
        "InstallPrivateInvigoratingSpellDescriptor",
        "Gameplay must resolve through the captured CGAL parent",
        "0x29",
        "SimulationClock()",
        "InstallBrewingControllerVtable",
        "BrewingControllerDestroyed",
        "LaboratoryControllerDestroyed",
        "MajestyControllerLifecycle::RegisterManagedVtable",
        "stock teardown boundary",
        "BrewingControllerControl",
        "BrewingControllerEvent",
        "AP24's active branch, in stock order",
        "AP24's inactive branch performs the exact inverse display swap",
        "stock Rage command metadata",
        "exact-handle private Rage GPL route",
        "invoking its private GPL clone",
        "kStockArrowsResearchControlId = 0x0000139C",
        "kWeaponOilResearchControlId = 0x00002A13",
        "kStockTeleportAmuletResearchControlId = 0x000013B3",
        "kPhoenixPhialResearchControlId = 0x00002A16",
        "kPhoenixPhialProgressControlId = 0x00002A17",
        "kPhoenixPhialActiveDisplayControlId = 0x00002A18",
        "refreshResearchRowsRva",
        "refreshSingleResearchRowRva",
        "canSubmitResearchRva",
        "submitResearchCommandRva",
        "ValidateStockResearchRoute",
        "RefreshWeaponOilResearch",
        "refreshSingleResearchRow(panel, context, kWeaponOilResearchControlId)",
        "auto canSubmitResearch = reinterpret_cast<CanSubmitResearch>",
        "Stock eligibility gate rejected %s research.",
        "BeginLaboratoryResearch",
        "LaboratoryResearchOwner",
        "CaptureLaboratoryActivity",
        "ClearLaboratoryActivity(context)",
        "RestoreLaboratoryActivity(context, liveActivity)",
        "Laboratory research rejected: its private owner is already active.",
        "researchCompletionRva",
        "researchCompletionDispatchSlotRva",
        "StageLaboratoryResearchForStockCompletion",
        "ResearchCompletionBridge",
        "stock Blacksmith event 0x2009 completion",
        "Observed native event 0x2009 complete Laboratory research",
        "HandleWeaponOilResearch",
        "submitResearchCommand(",
        "submitResearchCommand(commandOwner, context, recipe)",
        "private capture is %s.",
        "CaptureSubmittedLaboratoryResearch",
        "Captured queued Laboratory research 0x%08X tuple %u/%u and restored AP10 activity.",
        "HandlePhoenixPhialResearch",
        "kCurrentResearchAttributeId = 0x2C425041",
        "kStockArrowsResearchPrice = 250",
        "kWeaponOilResearchPrice = 250",
        "kPhoenixPhialResearchPrice = 750",
        "g_weaponOilResearchDescriptor[1] = 1",
        "g_phoenixPhialResearchDescriptor[1] = 2",
        "LaboratoryBuildingLevel",
        "kPhoenixPhialResearchIconControlId",
        "kPhoenixPhialResearchPriceControlId",
        "LaboratoryControllerActivity",
        "g_laboratoryResearchCompletionStaged",
        "This vtable exists only on CGAL",
        "A stock AP17 research completion never enters AP69's Fervus spell",
        "g_laboratoryResearchCompletedThisUpdate",
        "currentResearch == static_cast<int>(kWeaponOilResearchControlId)",
        "stockResearchRefresh",
        "argument3 >= 0x18000000 && argument3 <= 0x2B000000",
        "argument3 == kCurrentResearchAttributeId",
        "kWeaponOilProgressControlId = 0x00002A11",
        "kWeaponOilActiveDisplayControlId = 0x00002A12",
        "UpdateWeaponOilPresentation",
        "7, elapsed, 0, g_laboratoryResearchOwner.duration",
        "controller, kWeaponOilProgressControlId, 0x08, 0, 0"
        "researchCompletionNamePushRva"
        "expectedResearchCompletionNamePush"
        'const char g_weaponOilCompletionName[] = "Weapon Oil"'
        'const char g_phoenixPhialCompletionName[] = "Phoenix Phial"'
        "resolveResearchDescriptorRva"
        "expectedResolveResearchDescriptorEntry"
        "std::uint32_t* g_weaponOilResearchDescriptor = nullptr"
        "std::uint32_t* g_phoenixPhialResearchDescriptor = nullptr"
        "stockOperatorNew(kResearchDescriptorSize)"
        "g_weaponOilResearchDescriptor = nullptr"
        "g_phoenixPhialResearchDescriptor = nullptr"
        "RegisterPrivateResearchDescriptors"
        "g_researchDescriptorRegistryMap"
        "g_researchDescriptorRegistryFindOrInsert"
        "Re-resolve the private keys on every"
        "Re-registered Weapon Oil and Phoenix Phial after AP99 rebuilt its stock research registry."
        "AP99's stock Blacksmith research registry"
        "InstallPrivateWeaponOilResearchDescriptor"
        "stockArrows[3] != kArrowsGlobalTextId"
        "stockArrows[4] != 0x2A425041"
        "ResearchCompletionNamePushHook"
        "InstallResearchCompletionNameClone"
        "cmp ebx, dword ptr [g_weaponOilResearchDescriptor]"
        "Registered Weapon Oil and Phoenix Phial"
        "Installed scoped Weapon Oil name substitution"
        "ResolvePrivatePhoenixPhialDescriptor"
        "stock Teleportation Amulet descriptor"
        "cmp ebx, dword ptr [g_phoenixPhialResearchDescriptor]"
    )) {
        if (-not $runtimeSource.Contains($contract)) {
            throw "Runtime hook contract is missing: $contract"
        }
    }
    if ($runtimeSource -match
        'if\s*\(g_privateResearchDescriptorsRegistered\)\s*\{\s*return true;') {
        throw "Private AP99 registration must be revalidated after every stock registry rebuild."
    }
    $initializeStart = $runtimeSource.IndexOf("DWORD WINAPI InitializeRuntime(void*)")
    $initializeEnd = $runtimeSource.IndexOf("}  // namespace", $initializeStart)
    if ($initializeStart -lt 0 -or $initializeEnd -le $initializeStart) {
        throw "Runtime initialization lifecycle is missing."
    }
    $initializeRuntime = $runtimeSource.Substring(
        $initializeStart, $initializeEnd - $initializeStart)
    $readySignal = $initializeRuntime.IndexOf("SignalManagerRuntimeReady()")
    $windowHook = $initializeRuntime.IndexOf("InstallWindowProcedureHook()")
    if ($readySignal -lt 0 -or $windowHook -le $readySignal) {
        throw "Manager readiness must precede only the stock-window-dependent hook."
    }
    foreach ($requiredPreWindowInstall in @(
        "InstallPrivateIntentTextResolver()",
        "InstallFreestyleCamRuntime(",
        "InstallCustomGuildFactoryFallback()",
        "InstallPrivateNameGenerators()",
        "ValidateStockResearchRoute()",
        "InstallPrivateWeaponOilResearchDescriptor()",
        "InstallResearchCompletionBridge()",
        "InstallResearchCompletionNameClone()",
        "InstallPrivateInvigoratingSpellDescriptor()",
        "InstallPrivateSovereignSpellRoute()",
        "InstallPrivateRageRoute()",
        "InstallDialogCreationHook()",
        "InstallDialogFactoryTrace()",
        "InstallSecondaryControllerHook()",
        "InstallGameUpdateRefreshBridge()",
        "InstallPrivateEnchantmentRows()"
    )) {
        $installPosition = $initializeRuntime.IndexOf($requiredPreWindowInstall)
        if ($installPosition -lt 0 -or $installPosition -ge $readySignal) {
            throw "Required static install does not complete before manager readiness: $requiredPreWindowInstall"
        }
    }
    foreach ($managerRequiredInstall in @(
        "InstallFreestyleCamRuntime",
        "InstallCustomGuildFactoryFallback",
        "InstallPrivateNameGenerators",
        "ValidateStockResearchRoute",
        "InstallPrivateWeaponOilResearchDescriptor",
        "InstallResearchCompletionBridge",
        "InstallResearchCompletionNameClone",
        "InstallPrivateInvigoratingSpellDescriptor",
        "InstallPrivateSovereignSpellRoute",
        "InstallPrivateRageRoute",
        "InstallDialogCreationHook",
        "InstallDialogFactoryTrace",
        "InstallSecondaryControllerHook",
        "InstallGameUpdateRefreshBridge",
        "InstallPrivateEnchantmentRows",
        "InstallWindowProcedureHook"
    )) {
        $requiredPattern = "RequireManagerRuntimeInstall\(\s*" +
            [regex]::Escape($managerRequiredInstall) + "\("
        if (-not [regex]::IsMatch($initializeRuntime, $requiredPattern)) {
            throw "Manager launch does not fail closed for required install: $managerRequiredInstall"
        }
    }
    $capabilityGates = @(
        @{
            Condition = "privateActivityText"
            Calls = @(
                "LoadPrivateIntentRegistry()",
                "ValidatePrivateIntentTextProfile()",
                "InstallPrivateIntentTextResolver()"
            )
        },
        @{
            Condition = "freestyleCam"
            Calls = @("InstallFreestyleCamRuntime(")
        },
        @{
            Condition = "expandedBuildingSlots"
            Calls = @("InstallCustomGuildFactoryFallback()")
        },
        @{
            Condition = "alchemistNames || phantomNames"
            Calls = @("InstallPrivateNameGenerators()")
        },
        @{
            Condition = "alchemistOilRows"
            Calls = @("InstallPrivateEnchantmentRows()")
        },
        @{
            Condition = "alchemistSecondary"
            Calls = @(
                "ValidateStockResearchRoute()",
                "InstallPrivateWeaponOilResearchDescriptor()",
                "InstallResearchCompletionBridge()",
                "InstallResearchCompletionNameClone()",
                "InstallPrivateInvigoratingSpellDescriptor()",
                "InstallPrivateSovereignSpellRoute()",
                "InstallPrivateRageRoute()",
                "InstallDialogCreationHook()",
                "InstallDialogFactoryTrace()",
                "InstallSecondaryControllerHook()",
                "InstallGameUpdateRefreshBridge()",
                "InstallWindowProcedureHook()"
            )
        }
    )
    foreach ($gate in $capabilityGates) {
        $guardedText = (Get-CppGuardBlocks `
            -Source $initializeRuntime -Condition $gate.Condition) -join "`n"
        if ([string]::IsNullOrEmpty($guardedText)) {
            throw "Runtime capability guard is missing: $($gate.Condition)"
        }
        foreach ($call in $gate.Calls) {
            $allCount = ([regex]::Matches(
                $initializeRuntime, [regex]::Escape($call))).Count
            $guardedCount = ([regex]::Matches(
                $guardedText, [regex]::Escape($call))).Count
            if ($allCount -ne 1 -or $guardedCount -ne 1) {
                throw "Runtime call is not exclusively gated by $($gate.Condition): $call"
            }
        }
    }
    foreach ($alchemistInstaller in @(
        "InstallPrivateWeaponOilResearchDescriptor()",
        "InstallResearchCompletionBridge()",
        "InstallResearchCompletionNameClone()",
        "InstallPrivateInvigoratingSpellDescriptor()",
        "InstallPrivateSovereignSpellRoute()",
        "InstallPrivateRageRoute()",
        "InstallDialogCreationHook()",
        "InstallDialogFactoryTrace()",
        "InstallSecondaryControllerHook()",
        "InstallGameUpdateRefreshBridge()",
        "InstallPrivateEnchantmentRows()",
        "InstallWindowProcedureHook()"
    )) {
        $alchemistGuards = @(
            Get-CppGuardBlocks -Source $initializeRuntime -Condition "alchemistNames"
            Get-CppGuardBlocks -Source $initializeRuntime -Condition "alchemistSecondary"
            Get-CppGuardBlocks -Source $initializeRuntime -Condition "alchemistOilRows"
        ) -join "`n"
        $total = ([regex]::Matches(
            $initializeRuntime, [regex]::Escape($alchemistInstaller))).Count
        $guarded = ([regex]::Matches(
            $alchemistGuards, [regex]::Escape($alchemistInstaller))).Count
        if ($total -ne 1 -or $guarded -ne 1) {
            throw "Haunt-only/generic MMCP can reach an Alchemist installer: $alchemistInstaller"
        }
    }
    $absentManifest = Get-CppGuardBlocks `
        -Source $initializeRuntime `
        -Condition "capabilityManifest == CapabilityManifestState::Absent"
    if (($absentManifest -join "`n").IndexOf("return 0;") -lt 0) {
        throw "An injection without MMCP does not fail closed before optional hooks."
    }
    if ($initializeRuntime.IndexOf("if (!SignalManagerRuntimeReady())") -lt 0) {
        throw "Standard-only empty MMCP cannot release the suspended launcher without optional hooks."
    }
    if ($launcherSource.Contains("MAJESTY_MOD_MANAGER_INTENT_REGISTRY")) {
        throw "MMTX presence still acts as the launcher readiness marker; MMCP must be authoritative."
    }
    $launcherWait = $launcherSource.IndexOf("WaitForMultipleObjects(")
    $launcherResume = $launcherSource.IndexOf("ResumeThread(process.hThread)")
    if ($launcherWait -lt 0 -or $launcherResume -le $launcherWait) {
        throw "Launcher resumes Majesty before the manager runtime barrier completes."
    }
    $profileLifetimeWait = $launcherSource.IndexOf(
        "WaitForSingleObject(process.hProcess, INFINITE)")
    $profileLockClose = $launcherSource.LastIndexOf(
        "CloseProfileLock(&profileLock)")
    if ($profileLifetimeWait -le $launcherResume -or
        $profileLockClose -le $profileLifetimeWait) {
        throw "Launcher does not retain the inherited Merge-profile lock through Majesty exit."
    }
    foreach ($forbidden in @(
        "MessageBoxA",
        "SetTimer",
        "ShowBrewingPlaceholder",
        "kBrewingHeaderControlId",
        "kUiCommandRefreshRva",
        "uiCommandRefresh",
        'reinterpret_cast<std::uint32_t>("ALCHEMY LAB")',
        "The CGAL Brewing runtime hook intercepted Majesty's missing AP10"
        "kStockPalaceBuildingClassId"
        "sovereignCursorPresenterRva"
        "PresentSovereignCursor"
        "targetManager, cursorOrdinal, 0"
    )) {
        if ($runtimeSource.Contains($forbidden)) {
            throw "Obsolete Brewing diagnostic remains in the runtime: $forbidden"
        }
    }
    foreach ($contract in @(
        "kRegistryVersion = 1",
        "kFirstPrivateIntentId = 0x60000000u",
        "kLastPrivateIntentId = 0x6FFFFFFFu",
        "ParseRegistry",
        "registry record IDs are not strictly increasing",
        "registry contains trailing bytes",
        "valid non-NUL Windows-1252"
    )) {
        if (-not ($intentRegistrySource.Contains($contract) -or
                  $intentRegistryHeader.Contains($contract))) {
            throw "Intent-text registry contract is missing: $contract"
        }
    }
    foreach ($contract in @(
        "kManifestVersion = 1",
        "kMaximumCapabilityCount = 64",
        "kMaximumCapabilityBytes = 128",
        "kMaximumManifestBytes = 64u * 1024u",
        "ParseManifest",
        "capability names are not strictly increasing",
        "capability manifest contains trailing bytes",
        "capability is not supported by this runtime",
        'expanded-building-slots.cg-prefix',
        'freestyle-cam-rebind.v1',
        'private-activity-text-registry.v1',
        'generic-visitor-lists.v1',
        'alchemist.cgbrewing-secondary-controller',
        'alchemist.ap78-private-oil-rows',
        'alchemist.nm18-name-generator'
    )) {
        if (-not ($capabilitySource.Contains($contract) -or
                  $capabilityHeader.Contains($contract))) {
            throw "Runtime capability manifest contract is missing: $contract"
        }
    }
    if ($runtimeSource.Contains("ResolveResearchDescriptorHook")) {
        throw "Private research reverted to an incomplete call-site resolver hook."
    }
    $descriptorInstallStart = $runtimeSource.IndexOf(
        "bool InstallPrivateWeaponOilResearchDescriptor()")
    $descriptorInstallEnd = $runtimeSource.IndexOf(
        "bool InstallResearchCompletionBridge()",
        $descriptorInstallStart)
    if ($descriptorInstallStart -lt 0 -or
        $descriptorInstallEnd -le $descriptorInstallStart) {
        throw "The AP99 private research registry installation is missing."
    }
    $descriptorInstall = $runtimeSource.Substring(
        $descriptorInstallStart,
        $descriptorInstallEnd - $descriptorInstallStart)
    foreach ($forbiddenPatch in @("VirtualAlloc", "VirtualProtect", "FlushInstructionCache")) {
        if ($descriptorInstall.Contains($forbiddenPatch)) {
            throw "AP99 descriptor registration is patching its stock resolver: $forbiddenPatch"
        }
    }
    $completionDispatchStart = $descriptorInstallEnd
    $completionDispatchEnd = $runtimeSource.IndexOf(
        'extern "C" const std::uint32_t* __stdcall ResolvePrivateInvigoratingDescriptor()',
        $completionDispatchStart)
    if ($completionDispatchStart -lt 0 -or
        $completionDispatchEnd -le $completionDispatchStart) {
        throw "The stock event 0x2009 completion bridge installation is missing."
    }
    $completionDispatch = $runtimeSource.Substring(
        $completionDispatchStart,
        $completionDispatchEnd - $completionDispatchStart)
    foreach ($contract in @(
        "researchCompletionDispatchSlotRva",
        "dispatchSlot[-1] != 0x00002009u",
        "dispatchSlot[1] != 0x0000200Bu",
        "g_stockResearchCompletion",
        "&ResearchCompletionBridge"
    )) {
        if (-not $completionDispatch.Contains($contract)) {
            throw "Stock event 0x2009 completion bridge lost its dispatch contract: $contract"
        }
    }
    foreach ($contract in @(
        "struct FreestyleCamProfile",
        '"public-1.5.2.24"',
        '"beta2-1.5.2.28"',
        "kPublicFreestyleProfile",
        "kBeta2FreestyleProfile",
        "AcquireImage",
        "EnsureLiveRegistry",
        "PreflightProfile",
        "RollBackPatches",
        "WriteReleaseVtable8Patch",
        "kMajestyComVtableSpan = 0x00400000",
        "IsStockRenderWrapper",
        "HasStockVtableMethod",
        "stockCodeRva = g_profile->wrapperAssignRva",
        "IsGameCode(method18)",
        "ClearRegistryCache();",
        "__finally",
        "previous == incoming",
        '"upstream-parity"',
        "installed stock IMAG rebind and dead-wrapper teardown guards"
    )) {
        if (-not $freestyleSource.Contains($contract)) {
            throw "Freestyle runtime contract is missing: $contract"
        }
    }
    foreach ($forbidden in @(
        "Sleep(2000)",
        "version.dll",
        "Suppress registry destructor",
        "detour_wrap_use"
    )) {
        if ($freestyleSource.Contains($forbidden)) {
            throw "Rejected sidecar behavior remains in the integrated runtime: $forbidden"
        }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "licenses\FREESTYLE-CAM-SIDECAR.txt") -PathType Leaf)) {
        throw "The freestyle-cam-sidecar MIT notice is missing."
    }
    $runtimeDllText = [Text.Encoding]::ASCII.GetString(
        [IO.File]::ReadAllBytes((Join-Path $output "MajestyBuildingRuntime.dll")))
    if (-not $runtimeDllText.Contains("upstream-parity")) {
        throw "The default runtime DLL does not contain the validated upstream assignment mode."
    }
    foreach ($guard in @(
        @{ Name = "SafeReleasePointer"; Next = "void __stdcall SafeReleaseVtable8(" },
        @{ Name = "SafeReleaseVtable8"; Next = "__declspec(naked) void HandleUseHook(" }
    )) {
        $functionName = $guard.Name
        $start = $freestyleSource.IndexOf("void __stdcall $functionName(")
        $end = $freestyleSource.IndexOf($guard.Next, $start)
        if ($start -lt 0 -or $end -le $start) {
            throw "The upstream teardown guard is missing: $functionName"
        }
        $body = $freestyleSource.Substring($start, $end - $start)
        if (-not $body.Contains("ClearRegistryCache();") -or
            $body.Contains("if (pointer != 0)")) {
            throw "$functionName does not clear the registry cache for every non-live pointer."
        }
    }
    $handleStart = $runtimeSource.IndexOf("int HandleInvigoratingElixer(")
    $handleEnd = $runtimeSource.IndexOf("__declspec(naked) void RageCommandDispatchHook", $handleStart)
    $laboratoryStart = $runtimeSource.IndexOf("int __fastcall LaboratoryControllerControl(")
    $laboratoryEnd = $runtimeSource.IndexOf("bool InstallLaboratoryControllerVtable", $laboratoryStart)
    $rageGuard = "Ignored Invigorating Elixer while stock Rage owns the Palace count."
    if ($handleStart -lt 0 -or $handleEnd -le $handleStart -or
        -not $runtimeSource.Substring($handleStart, $handleEnd - $handleStart).Contains($rageGuard)) {
        throw "Stock Rage exclusion guard is not scoped to the Vigor action handler."
    }
    $vigorHandler = $runtimeSource.Substring($handleStart, $handleEnd - $handleStart)
    $affordabilityGate = $vigorHandler.IndexOf("StockCurrentPlayerGold()")
    $commandSubmission = $vigorHandler.IndexOf("submitBuildingCommand(")
    $activePublication = $vigorHandler.IndexOf(
        'InterlockedExchange(&g_invigoratingElixerActive, 1)')
    if ($affordabilityGate -lt 0 -or $commandSubmission -le $affordabilityGate -or
        $activePublication -le $commandSubmission) {
        throw "Vigor does not run AP24's stock affordability gate before command submission and active publication."
    }
    if ($laboratoryStart -lt 0 -or $laboratoryEnd -le $laboratoryStart -or
        $runtimeSource.Substring($laboratoryStart, $laboratoryEnd - $laboratoryStart).Contains($rageGuard)) {
        throw "Stock Rage exclusion guard leaked into the parent Laboratory controller."
    }
    $initializeStart = $runtimeSource.IndexOf("DWORD WINAPI InitializeRuntime(")
    $initializeEnd = $runtimeSource.IndexOf("}  // namespace", $initializeStart)
    if ($initializeStart -lt 0 -or $initializeEnd -le $initializeStart) {
        throw "Runtime initialization function is missing."
    }
    $initialize = $runtimeSource.Substring(
        $initializeStart, $initializeEnd - $initializeStart)
    if (-not [regex]::IsMatch(
            $initialize,
            "RequireManagerRuntimeInstall\(\s*InstallPrivateInvigoratingSpellDescriptor\(\)") -or
        -not [regex]::IsMatch(
            $initialize,
            "RequireManagerRuntimeInstall\(\s*InstallPrivateSovereignSpellRoute\(\)")) {
        throw "Private sovereign targeting is not installed fail-closed after its descriptor resolver."
    }
    if (-not [regex]::IsMatch(
            $initialize,
            "RequireManagerRuntimeInstall\(\s*InstallFreestyleCamRuntime\(g_runtimeModule, g_buildProfile->id\)")) {
        throw "The Freestyle CAM lifecycle repair is not installed fail-closed after profile validation."
    }
    $laboratoryControl = $runtimeSource.Substring(
        $laboratoryStart, $laboratoryEnd - $laboratoryStart)
    if (-not $laboratoryControl.Contains(
        'InterlockedExchange(&g_cgalSecondaryArmed, 1);')) {
        throw "CGAL secondary mapping is not armed by AP10's private Brewing command."
    }
    $upgradeGuard = $laboratoryControl.IndexOf(
        "if (controlId == kBuildingUpgradeControlId)")
    $stockLaboratoryControl = $laboratoryControl.IndexOf(
        "return g_stockLaboratoryControl(controller, controlId);")
    if ($upgradeGuard -lt 0 -or $stockLaboratoryControl -le $upgradeGuard -or
        -not $laboratoryControl.Contains(
            "if (!LaboratoryUpgradeResearchComplete(context))") -or
        -not $laboratoryControl.Contains(
            "ApplyLaboratoryUpgradeResearchGate(")) {
        throw "Laboratory upgrade does not reject unmet research before AP10's stock click path."
    }
    $upgradeGateStart = $runtimeSource.IndexOf(
        "void ApplyLaboratoryUpgradeResearchGate(")
    $upgradeGateEnd = $runtimeSource.IndexOf(
        "void RefreshWeaponOilResearch(", $upgradeGateStart)
    if ($upgradeGateStart -lt 0 -or $upgradeGateEnd -le $upgradeGateStart) {
        throw "Laboratory upgrade presentation gate is missing."
    }
    $upgradeGate = $runtimeSource.Substring(
        $upgradeGateStart, $upgradeGateEnd - $upgradeGateStart)
    foreach ($contract in @(
        "controller, kBuildingUpgradeControlId, 0x0A, 1, 0",
        "controller, kBuildingUpgradePriceControlId, false"
    )) {
        if (-not $upgradeGate.Contains($contract)) {
            throw "Laboratory upgrade gate lost the stock Guardhouse presentation contract: $contract"
        }
    }
    $presentationStart = $runtimeSource.IndexOf("void UpdateBrewingPresentation(")
    $presentationEnd = $runtimeSource.IndexOf(
        "bool CaptureSubmittedLaboratoryResearch(", $presentationStart)
    if ($presentationStart -lt 0 -or $presentationEnd -le $presentationStart) {
        throw "The Brewing presentation function is missing."
    }
    $presentation = $runtimeSource.Substring(
        $presentationStart, $presentationEnd - $presentationStart)
    if (-not $presentation.Contains("StockRageOfKrolmCount() != 0")) {
        throw "Vigor lost AP24's Palace-owned Rage exclusion gate."
    }
    if (-not $runtimeSource.Contains(
        "panel, player, kInvigoratingElixerControlId, 0")) {
        throw "Private Vigor row is not using AP69's exact stock presenter."
    }
    $sovereignActionStart = $runtimeSource.IndexOf(
        "int HandlePhilosophersStone(")
    $sovereignActionEnd = $runtimeSource.IndexOf(
        "int HandleWeaponOilResearch(", $sovereignActionStart)
    if ($sovereignActionEnd -lt 0) {
        $sovereignActionEnd = $runtimeSource.IndexOf(
            "// 0x004A7F40 constructs stock Arrows",
            $sovereignActionStart)
    }
    if ($sovereignActionStart -lt 0 -or $sovereignActionEnd -le $sovereignActionStart) {
        throw "The private sovereign action handler is missing."
    }
    $sovereignAction = $runtimeSource.Substring(
        $sovereignActionStart, $sovereignActionEnd - $sovereignActionStart)
    if (-not $sovereignAction.Contains("beginSovereignTarget(privateControlId);") -or
        $sovereignAction.Contains("PresentSovereignCursor") -or
        $sovereignAction.Contains("targetManager")) {
        throw "Private actions must enter the complete stock temple target mode without an early cursor repaint."
    }
    $cursorHookStart = $runtimeSource.IndexOf(
        "__declspec(naked) void SovereignCursorTransitionHook()")
    $cursorHookEnd = $runtimeSource.IndexOf(
        'extern "C" void __cdecl SubmitPrivateSovereignCommand(',
        $cursorHookStart)
    if ($cursorHookStart -lt 0 -or $cursorHookEnd -le $cursorHookStart) {
        throw "The scoped stock cursor transition clone is missing."
    }
    $cursorHook = $runtimeSource.Substring(
        $cursorHookStart, $cursorHookEnd - $cursorHookStart)
    foreach ($contract in @(
        "mov edx, dword ptr [esi]",
        "mov edx, dword ptr [edx + 48h]",
        "cmp dword ptr [g_pendingSovereignControl], 2A21h",
        "cmp dword ptr [edi], 33327053h",
        "call edx",
        "jmp dword ptr [g_sovereignCursorTransitionResume]"
    )) {
        if (-not $cursorHook.Contains($contract)) {
            throw "Scoped sovereign cursor clone is missing: $contract"
        }
    }
    $sovereignDescriptorStart = $runtimeSource.IndexOf(
        'extern "C" const std::uint32_t* __stdcall ResolvePrivateSovereignDescriptor(')
    $sovereignDescriptorEnd = $runtimeSource.IndexOf(
        "__declspec(naked) void ResolveSpellDescriptorHook()",
        $sovereignDescriptorStart)
    if ($sovereignDescriptorStart -lt 0 -or
        $sovereignDescriptorEnd -le $sovereignDescriptorStart) {
        throw "The private stock temple descriptor clone is missing."
    }
    $sovereignDescriptor = $runtimeSource.Substring(
        $sovereignDescriptorStart,
        $sovereignDescriptorEnd - $sovereignDescriptorStart)
    foreach ($contract in @(
        "kStockVinesControlId",
        "kStockFervusBuildingClassId",
        "kStockVinesMode",
        "descriptor[2] = stockMode;"
    )) {
        if (-not $sovereignDescriptor.Contains($contract)) {
            throw "Private descriptor lost its stock temple contract: $contract"
        }
    }
    if ($sovereignDescriptor.Contains("kStockLightningStormControlId")) {
        throw "Private targeting still resolves through Wizard Lightning Storm."
    }
    $spellHookStart = $runtimeSource.IndexOf(
        "__declspec(naked) void ResolveSpellDescriptorHook()")
    $spellHookEnd = $runtimeSource.IndexOf(
        "bool InstallPrivateInvigoratingSpellDescriptor()",
        $spellHookStart)
    $spellHook = $runtimeSource.Substring(
        $spellHookStart, $spellHookEnd - $spellHookStart)
    foreach ($contract in @(
        "cmp dword ptr [esp + 4], 1132h",
        "cmp dword ptr [g_customBrewingActive], 1",
        "jne stock_resolver",
        "jmp dword ptr [g_resolveSpellDescriptorTrampoline]"
    )) {
        if (-not $spellHook.Contains($contract)) {
            throw "Stock Vines fallback after private-controller teardown is missing: $contract"
        }
    }
    $sovereignSubmitStart = $runtimeSource.IndexOf(
        'extern "C" void __cdecl SubmitPrivateSovereignCommand(')
    $sovereignSubmitEnd = $runtimeSource.IndexOf(
        "__declspec(naked) void PublicSovereignExecutorHook()",
        $sovereignSubmitStart)
    $sovereignSubmit = $runtimeSource.Substring(
        $sovereignSubmitStart,
        $sovereignSubmitEnd - $sovereignSubmitStart)
    foreach ($contract in @(
        "mode == kStockVinesMode",
        "cost = kStockUnaffordableGoldCost;",
        "mode = kPhilosophersStoneMode;",
        "target = laboratory;",
        "cost = 0;"
    )) {
        if (-not $sovereignSubmit.Contains($contract)) {
            throw "Private submit lost its stock-to-private boundary: $contract"
        }
    }
    foreach ($forbidden in @(
        "CancelSovereignTargetMode",
        "kSovereignNoTargetMode",
        "CancelSovereignTargetWithoutSelection"
    )) {
        if ($sovereignSubmit.Contains($forbidden) -or $runtimeSource.Contains($forbidden)) {
            throw "Private depleted-cast handling retained obsolete target cancellation: $forbidden"
        }
    }
    if ([regex]::IsMatch(
        $presentation,
        'kInvigoratingElixerControlId,\s*0x0A,\s*(?:0u|false),')) {
        throw "Custom presentation is re-enabling Vigor after AP69's stock level gate."
    }
    if ($presentation.Contains(
        'controller, kPhoenixPhialResearchControlId, true')) {
        throw "Custom presentation is re-showing Phoenix after AP99's stock level gate."
    }
    if (-not $presentation.Contains(
        "const bool vigorLevelAvailable = LaboratoryBuildingLevel(context) >= 3") -or
        -not $presentation.Contains(
            "if (active && vigorLevelAvailable)") -or
        -not $presentation.Contains(
            "controller, kInvigoratingElixerIconControlId, vigorLevelAvailable") -or
        -not $runtimeSource.Contains(
            "const bool levelAvailable = LaboratoryBuildingLevel(context) >= 3")) {
        throw "Level-3 Brewing content no longer follows the stock hidden-until-tier presentation."
    }
    $researchPresentationStart = $runtimeSource.IndexOf(
        "void UpdateWeaponOilPresentation(")
    $researchPresentationEnd = $runtimeSource.IndexOf(
        "int StockRageOfKrolmCount(", $researchPresentationStart)
    if ($researchPresentationStart -lt 0 -or
        $researchPresentationEnd -le $researchPresentationStart) {
        throw "Laboratory active-research presentation functions are missing."
    }
    $researchPresentation = $runtimeSource.Substring(
        $researchPresentationStart,
        $researchPresentationEnd - $researchPresentationStart)
    foreach ($researchPriceControl in @(
        "kWeaponOilResearchPriceControlId, false",
        "kPhoenixPhialResearchPriceControlId, false"
    )) {
        if (-not $researchPresentation.Contains($researchPriceControl)) {
            throw "Active research display is not hiding its stock price child: $researchPriceControl"
        }
    }
    $reagentMeterStart = $runtimeSource.IndexOf(
        "void UpdateLaboratoryReagentMeter(")
    $reagentMeterEnd = $runtimeSource.IndexOf(
        "void RefreshSovereignBrewingRow(", $reagentMeterStart)
    if ($reagentMeterStart -lt 0 -or $reagentMeterEnd -le $reagentMeterStart) {
        throw "Laboratory Reagent meter presentation is missing."
    }
    $reagentMeter = $runtimeSource.Substring(
        $reagentMeterStart, $reagentMeterEnd - $reagentMeterStart)
    if ($reagentMeter.Contains("LaboratoryBuildingLevel") -or
        -not $reagentMeter.Contains(
            "controller, kReagentMeterLabelControlId, true") -or
        -not $reagentMeter.Contains(
            "controller, kReagentMeterCountControlId, true")) {
        throw "Laboratory Reagent storage must remain visible at every building level."
    }
    $researchOwnerStart = $runtimeSource.IndexOf("int BeginLaboratoryResearch(")
    $researchOwnerEnd = $runtimeSource.IndexOf("int HandleWeaponOilResearch(", $researchOwnerStart)
    if ($researchOwnerStart -lt 0 -or $researchOwnerEnd -le $researchOwnerStart) {
        throw "The private Laboratory research owner is missing."
    }
    $researchOwner = $runtimeSource.Substring(
        $researchOwnerStart, $researchOwnerEnd - $researchOwnerStart)
    foreach ($contract in @(
        "if (LaboratoryResearchIsActive())",
        "const LaboratoryActivitySnapshot liveActivity",
        "ClearLaboratoryActivity(context);",
        "canSubmitResearch(reinterpret_cast<void*>(controller), recipe)",
        "submitResearchCommand(commandOwner, context, recipe);",
        "g_laboratoryResearchOwner.pending = true;",
        "const bool capturedSynchronously",
        "CaptureSubmittedLaboratoryResearch(liveActivity)",
        "RestoreLaboratoryActivity(context, liveActivity);"
    )) {
        if (-not $researchOwner.Contains($contract)) {
            throw "Laboratory research ownership contract is missing: $contract"
        }
    }
    $completionRestore = $runtimeSource.IndexOf(
        "&g_laboratoryResearchCompletedThisUpdate, 0)")
    $completionRefresh = $runtimeSource.IndexOf(
        "RefreshPhoenixPhialResearch(controller);", $completionRestore)
    $completionGuardRelease = $runtimeSource.IndexOf(
        "InterlockedExchange(&g_laboratoryResearchCompletionStaged, 0);",
        $completionRestore)
    $completionFrameReturn = $runtimeSource.IndexOf(
        "return;", $completionGuardRelease)
    $genericPresentation = $runtimeSource.IndexOf(
        "UpdateBrewingPresentation(controller);", $completionGuardRelease)
    if ($completionRestore -lt 0 -or $completionRefresh -lt 0 -or
        $completionGuardRelease -lt $completionRefresh -or
        $completionFrameReturn -lt $completionGuardRelease -or
        ($genericPresentation -ge 0 -and
            $completionFrameReturn -gt $genericPresentation)) {
        throw "AP10 completion guard must remain asserted through AP99 row restoration."
    }
    foreach ($forbiddenGate in @(
        "SetCompleteRecipeRowAvailability",
        "ApplyBrewingLevelGates",
        "LaboratoryBuildingLevel()"
    )) {
        if ($runtimeSource.Contains($forbiddenGate)) {
            throw "Non-stock recipe gate remains in the runtime: $forbiddenGate"
        }
    }
    $queuedCaptureStart = $runtimeSource.IndexOf(
        "bool CaptureSubmittedLaboratoryResearch(")
    $queuedCaptureEnd = $runtimeSource.IndexOf(
        "void StageLaboratoryResearchForStockCompletion(", $queuedCaptureStart)
    if ($queuedCaptureStart -lt 0 -or $queuedCaptureEnd -le $queuedCaptureStart) {
        throw "The queued stock-research capture bridge is missing."
    }
    $queuedCapture = $runtimeSource.Substring(
        $queuedCaptureStart, $queuedCaptureEnd - $queuedCaptureStart)
    foreach ($contract in @(
        "CaptureLaboratoryActivity(g_laboratoryResearchOwner.context)",
        "RestoreLaboratoryActivity(",
        "g_laboratoryResearchOwner.pending = false;",
        "g_laboratoryResearchOwner.active = true;"
    )) {
        if (-not $queuedCapture.Contains($contract)) {
            throw "Queued stock-research capture contract is missing: $contract"
        }
    }
    $gameUpdateStart = $runtimeSource.IndexOf(
        "void __fastcall GameUpdateRefreshBridge(")
    $gameUpdateEnd = $runtimeSource.IndexOf(
        "bool InstallGameUpdateRefreshBridge()", $gameUpdateStart)
    $gameUpdateBridge = $runtimeSource.Substring(
        $gameUpdateStart, $gameUpdateEnd - $gameUpdateStart)
    if ($gameUpdateBridge.IndexOf("activityBeforeUpdate") -gt
            $gameUpdateBridge.IndexOf("g_stockGameUpdate(gameState);") -or
        $gameUpdateBridge.IndexOf("CaptureSubmittedLaboratoryResearch(activityBeforeUpdate)") -lt
            $gameUpdateBridge.IndexOf("g_stockGameUpdate(gameState);")) {
        throw "Queued research is not captured around the stock game update."
    }
    if ($gameUpdateBridge.Contains("StageLaboratoryResearchForStockCompletion();") -or
        -not $gameUpdateBridge.Contains("g_laboratoryResearchCompletedThisUpdate")) {
        throw "Research completion is not owned by the stock event 0x2009 bridge."
    }
    $completionStart = $runtimeSource.IndexOf("void StageLaboratoryResearchForStockCompletion(")
    $completionEnd = $runtimeSource.IndexOf("void __fastcall GameUpdateRefreshBridge", $completionStart)
    if ($completionStart -lt 0 -or $completionEnd -le $completionStart) {
        throw "The private Laboratory completion bridge is missing."
    }
    $completionOwner = $runtimeSource.Substring(
        $completionStart, $completionEnd - $completionStart)
    if (-not $completionOwner.Contains("ResearchCompletionBridge") -or
        -not $completionOwner.Contains("g_stockResearchCompletion(") -or
        -not $completionOwner.Contains("eventType == 2") -or
        -not $completionOwner.Contains("CaptureLaboratoryActivity(context)") -or
        -not $completionOwner.Contains("RestoreLaboratoryActivity(context, liveActivity);") -or
        -not $completionOwner.Contains("StageLaboratoryResearchForStockCompletion();") -or
        $completionOwner.Contains("elapsed + 1000") -or
        $completionOwner.Contains("completeResearch(")) {
        throw "Stock event 0x2009 completion does not preserve and restore AP10 recruitment activity."
    }
    $updateStart = $runtimeSource.IndexOf("void UpdateBrewingPresentation(")
    $updateEnd = $runtimeSource.IndexOf("void StageLaboratoryResearchForStockCompletion(", $updateStart)
    if ($updateStart -lt 0 -or $updateEnd -le $updateStart -or
        $runtimeSource.Substring($updateStart, $updateEnd - $updateStart).Contains(
            "RefreshWeaponOilResearch")) {
        throw "Weapon Oil research is being repainted by the general game-update path."
    }
    $activityStart = $runtimeSource.IndexOf("void __fastcall LaboratoryControllerActivity(")
    $activityEnd = $runtimeSource.IndexOf("bool InstallLaboratoryControllerVtable", $activityStart)
    if ($activityStart -lt 0 -or $activityEnd -le $activityStart -or
        $runtimeSource.Substring($activityStart, $activityEnd - $activityStart).Contains(
            "RefreshWeaponOilResearch")) {
        throw "AP10's compatibility guard is repainting the native research row."
    }
    $laboratoryActivity = $runtimeSource.Substring(
        $activityStart, $activityEnd - $activityStart)
    $stockActivityRefresh = $laboratoryActivity.LastIndexOf(
        "g_stockLaboratoryActivity(controller);")
    $privateUpgradeRefresh = $laboratoryActivity.LastIndexOf(
        "ApplyLaboratoryUpgradeResearchGate(")
    if ($stockActivityRefresh -lt 0 -or
        $privateUpgradeRefresh -le $stockActivityRefresh) {
        throw "Laboratory upgrade gate must run after AP10's stock activity presenter."
    }
    $laboratoryEventStart = $runtimeSource.IndexOf(
        "void __fastcall LaboratoryControllerEvent(")
    $laboratoryEventEnd = $runtimeSource.IndexOf(
        "bool InstallLaboratoryControllerVtable",
        $laboratoryEventStart)
    if ($laboratoryEventStart -lt 0 -or
        $laboratoryEventEnd -le $laboratoryEventStart) {
        throw "Laboratory stock event-refresh lifecycle is missing."
    }
    $laboratoryEvent = $runtimeSource.Substring(
        $laboratoryEventStart,
        $laboratoryEventEnd - $laboratoryEventStart)
    $stockEventRefresh = $laboratoryEvent.IndexOf(
        "g_stockLaboratoryEvent(")
    $eventUpgradeGate = $laboratoryEvent.IndexOf(
        "ApplyLaboratoryUpgradeResearchGate(")
    if ($stockEventRefresh -lt 0 -or
        $eventUpgradeGate -le $stockEventRefresh) {
        throw "Laboratory upgrade gate must run after AP10's stock event presenter."
    }
    $laboratorySetupStart = $runtimeSource.IndexOf(
        "void __fastcall LaboratoryControllerSetup(")
    $laboratorySetupEnd = $runtimeSource.IndexOf(
        "void __fastcall LaboratoryControllerActivity(",
        $laboratorySetupStart)
    if ($laboratorySetupStart -lt 0 -or
        $laboratorySetupEnd -le $laboratorySetupStart) {
        throw "Laboratory post-insertion setup lifecycle is missing."
    }
    $laboratorySetup = $runtimeSource.Substring(
        $laboratorySetupStart,
        $laboratorySetupEnd - $laboratorySetupStart)
    $stockSetup = $laboratorySetup.IndexOf(
        "g_stockLaboratorySetup(controller);")
    $selectedContext = $laboratorySetup.IndexOf(
        "getPanelContext(controller)")
    $setupUpgradeGate = $laboratorySetup.IndexOf(
        "ApplyLaboratoryUpgradeResearchGate(")
    if ($stockSetup -lt 0 -or
        $selectedContext -le $stockSetup -or
        $setupUpgradeGate -le $selectedContext) {
        throw "CGAL must apply the stock Guardhouse gate after AP10's final setup presenter."
    }
    $installLaboratoryStart = $runtimeSource.IndexOf(
        "bool InstallLaboratoryControllerVtable(")
    $installLaboratoryEnd = $runtimeSource.IndexOf(
        'extern "C" void __stdcall CaptureSecondaryController(',
        $installLaboratoryStart)
    if ($installLaboratoryStart -lt 0 -or
        $installLaboratoryEnd -le $installLaboratoryStart) {
        throw "Laboratory controller installation lifecycle is missing."
    }
    $installLaboratory = $runtimeSource.Substring(
        $installLaboratoryStart,
        $installLaboratoryEnd - $installLaboratoryStart)
    foreach ($setupContract in @(
        "g_stockLaboratorySetup =",
        "reinterpret_cast<ControllerSetup>(stockVtable[1])",
        "g_customLaboratoryVtable[1] =",
        "reinterpret_cast<void*>(&LaboratoryControllerSetup)",
        "g_stockLaboratoryEvent =",
        "reinterpret_cast<ControllerEvent>(stockVtable[8])",
        "g_customLaboratoryVtable[8] =",
        "reinterpret_cast<void*>(&LaboratoryControllerEvent)"
    )) {
        if (-not $installLaboratory.Contains($setupContract)) {
            throw "CGAL lost its stock slot-1 setup lifecycle clone: $setupContract"
        }
    }
    if ($installLaboratory.Contains(
            "ApplyLaboratoryUpgradeResearchGate(controller, context);")) {
        throw "CGAL applies its upgrade gate at the pre-insertion factory result instead of stock setup completion."
    }
    $clearControllerStart = $runtimeSource.IndexOf(
        "void ClearBrewingControllerOwnedState()")
    $clearControllerEnd = $runtimeSource.IndexOf(
        "void __cdecl BrewingControllerDestroyed",
        $clearControllerStart)
    $clearController = $runtimeSource.Substring(
        $clearControllerStart, $clearControllerEnd - $clearControllerStart)
    foreach ($ownedState in @(
        "g_customBrewingActive",
        "g_customBrewingHandle",
        "g_captureBrewingController",
        "g_pendingSovereignControl",
        "g_pendingSovereignLaboratory"
    )) {
        if (-not $clearController.Contains($ownedState)) {
            throw "Secondary-controller teardown does not invalidate owned state: $ownedState"
        }
    }
    $parentTeardownStart = $runtimeSource.IndexOf(
        "void __cdecl LaboratoryControllerDestroyed")
    $parentTeardownEnd = $runtimeSource.IndexOf(
        "bool InstallLaboratoryControllerVtable",
        $parentTeardownStart)
    $parentTeardown = $runtimeSource.Substring(
        $parentTeardownStart, $parentTeardownEnd - $parentTeardownStart)
    foreach ($ownedState in @(
        "g_cgalControllerContext",
        "g_ap10ControllerContext",
        "g_customBrewingController",
        "ClearBrewingControllerOwnedState()"
    )) {
        if (-not $parentTeardown.Contains($ownedState)) {
            throw "Parent-controller teardown does not invalidate dependent state: $ownedState"
        }
    }
    Write-Host "Majesty Mod Manager native runtime tests passed."
}
finally {
    if (Test-Path -LiteralPath $output) {
        Remove-Item -LiteralPath $output -Recurse -Force
    }
}
