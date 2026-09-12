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
    if ($machine -ne 0x014C) {
        throw "$Path is not x86 (machine 0x$($machine.ToString('X4')))."
    }
    $isDll = ($characteristics -band 0x2000) -ne 0
    if ($isDll -ne $ExpectDll) {
        throw "$Path DLL characteristic does not match expectation."
    }
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
                if ($depth -eq 0) { $end = $index; break }
            }
        }
        if ($end -lt 0) { throw "Unterminated C++ guard: $Condition" }
        $blocks.Add($Source.Substring($start, $end - $start + 1))
        $cursor = $end + 1
    }
    return $blocks
}

function Assert-ContainsAny {
    param(
        [Parameter(Mandatory = $true)][string[]]$Sources,
        [Parameter(Mandatory = $true)][string[]]$Contracts,
        [Parameter(Mandatory = $true)][string]$Label
    )
    foreach ($contract in $Contracts) {
        $found = $false
        foreach ($source in $Sources) {
            if ($source.Contains($contract)) { $found = $true; break }
        }
        if (-not $found) { throw "$Label is missing: $contract" }
    }
}

function Get-SourceSpan {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Start,
        [Parameter(Mandatory = $true)][string]$End
    )
    $startIndex = $Source.IndexOf($Start, [StringComparison]::Ordinal)
    $endIndex = $Source.IndexOf($End, $startIndex + $Start.Length, [StringComparison]::Ordinal)
    if ($startIndex -lt 0 -or $endIndex -le $startIndex) {
        throw "Source lifecycle span is missing: $Start -> $End"
    }
    return $Source.Substring($startIndex, $endIndex - $startIndex)
}

function Assert-Ordered {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string[]]$Needles,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $cursor = -1
    foreach ($needle in $Needles) {
        $next = $Source.IndexOf($needle, $cursor + 1, [StringComparison]::Ordinal)
        if ($next -lt 0) { throw "$Label lost ordered step: $needle" }
        $cursor = $next
    }
}

try {
    & $buildScript -OutputRoot $output
    Assert-X86Pe (Join-Path $output "MajestyBuildingRuntime.dll") $true
    Assert-X86Pe (Join-Path $output "MajestyBuildingRuntimeLauncher.exe") $false

    $runtimeSource = Get-Content -Raw (Join-Path $repoRoot "runtime\MajestyModManagerRuntime.cpp")
    $lifecycleSource = Get-Content -Raw (Join-Path $repoRoot "runtime\ControllerLifecycleRegistry.cpp")
    $lifecycleHeader = Get-Content -Raw (Join-Path $repoRoot "runtime\ControllerLifecycleRegistry.h")
    $intentSource = Get-Content -Raw (Join-Path $repoRoot "runtime\IntentTextRegistry.cpp")
    $intentHeader = Get-Content -Raw (Join-Path $repoRoot "runtime\IntentTextRegistry.h")
    $capabilitySource = Get-Content -Raw (Join-Path $repoRoot "runtime\RuntimeCapabilityManifest.cpp")
    $capabilityHeader = Get-Content -Raw (Join-Path $repoRoot "runtime\RuntimeCapabilityManifest.h")
    $featureSource = Get-Content -Raw (Join-Path $repoRoot "runtime\RuntimeFeatureRegistry.cpp")
    $featureHeader = Get-Content -Raw (Join-Path $repoRoot "runtime\RuntimeFeatureRegistry.h")
    $controllerSource = Get-Content -Raw (Join-Path $repoRoot "runtime\StockControllerRegistry.cpp")
    $controllerHeader = Get-Content -Raw (Join-Path $repoRoot "runtime\StockControllerRegistry.h")
    $freestyleSource = Get-Content -Raw (Join-Path $repoRoot "runtime\FreestyleCamRuntime.cpp")
    $launcherSource = Get-Content -Raw (Join-Path $repoRoot "runtime\MajestyBuildingRuntimeLauncher.cpp")
    $probeSource = Get-Content -Raw (Join-Path $repoRoot "scripts\Launch-RuntimeProbe.ps1")
    $crashProbeSource = Get-Content -Raw (Join-Path $repoRoot "scripts\Launch-CrashCaptureProbe.ps1")

    Assert-ContainsAny @($launcherSource) @(
        "QuoteCommandLineArgument", "[game arguments...]",
        "for (int index = 3; index < argc; ++index)",
        "MAJESTY_MOD_MANAGER_CAPABILITIES",
        "MAJESTY_MOD_MANAGER_PROFILE_LOCK_HANDLE",
        "MAJESTY_BUILDING_RUNTIME_READY_EVENT", "ReadInheritedProfileLock",
        "GetHandleInformation", "FILE_TYPE_DISK", "WaitForMultipleObjects",
        "ResumeThread(process.hThread)",
        "WaitForSingleObject(injection, 30000)",
        "TerminateProcess(process.hProcess, 6)",
        "WaitForSingleObject(process.hProcess, INFINITE)",
        "CloseProfileLock(&profileLock)"
    ) "Runtime launcher contract"
    if ($launcherSource.Contains("WaitForSingleObject(injection, INFINITE)")) {
        throw "Runtime DLL injection can still wait forever."
    }
    if (-not $probeSource.Contains('[string[]]$GameArguments = @()') -or
        -not $probeSource.Contains('$launcher $game $dll @GameArguments')) {
        throw "Runtime probe does not forward optional game arguments."
    }
    Assert-ContainsAny @($crashProbeSource) @(
        'Windows Error Reporting\LocalDumps\MajestyHD.exe',
        '$dumpKey.SetValue("DumpType", 2', '$dumpKey.SetValue("DumpFolder", $session',
        'autosave-before.GMP', 'autosave-after.GMP', 'gpl.log',
        'gpl-session.log', 'majestyhd_crash_*.mdmp',
        '[string[]]$GameArguments = @("-debugout")'
    ) "Crash-capture probe contract"
    [void][scriptblock]::Create($crashProbeSource)

    Assert-ContainsAny @($lifecycleSource, $lifecycleHeader) @(
        "RegisterManagedVtable", "ManagedControllerDestructor",
        "InterlockedCompareExchange", "registration->stockDestructor(controller, deleteFlags)",
        "HeapAlloc", "InterlockedExchangePointer"
    ) "Generic controller lifecycle contract"
    Assert-ContainsAny @($intentSource, $intentHeader) @(
        "kRegistryVersion = 1", "kFirstPrivateIntentId = 0x60000000u",
        "kLastPrivateIntentId = 0x6FFFFFFFu", "ParseRegistry",
        "registry record IDs are not strictly increasing",
        "registry contains trailing bytes", "valid non-NUL Windows-1252"
    ) "Intent-text registry contract"
    Assert-ContainsAny @($featureSource, $featureHeader) @(
        "kRegistryVersion = 1", "kMaximumNameGeneratorCount = 256",
        "kMaximumEnchantmentRowCount = 1024", "kMaximumDisplayTextBytes = 512",
        "kMaximumRegistryBytes = 1024u * 1024u", "ParseRegistry",
        "generator IDs are not strictly increasing", "overlay IDs are not strictly increasing",
        "runtime feature registry contains trailing bytes", "FindEnchantmentRow"
    ) "Runtime feature registry contract"
    Assert-ContainsAny @($controllerSource, $controllerHeader) @(
        "kRegistryVersion = 10", "kMaximumRecordCount = 256",
        "kMaximumPanelCount = 32", "kMaximumRegistryBytes = 512u * 1024u",
        "ParseRegistry", "FindPanelByParentDialog", "FindPanelByChildDialog",
        "FindRewardPanelByParentDialog", "FindHostileMonsterFlagByMode",
        "FindPanelByParentCommand", "FindSovereignByPrivateMode",
        "kProvenSovereignExecutorMode = 0x34317053u",
        "kFirstStockAp99ControlId = 0x00001388u",
        "kAfterLastStockAp99ControlId = 0x000013ECu",
        "IsStockAp99ControlId(item.actionControlId)",
        "HasFourCCPrefix(item.privateMode, 'S', 'p')",
        "MMCR private sovereign mode collides with a stock mode",
        "!buildingFamilies.insert(item->buildingFamilyId).second",
        "stockTargetModes.find(*mode)", "stockExecutorModes.find(*mode)",
        "FindQuestBoardByCommand", "MMCR v9 quest boards contain a non-stock duplicate Refresh row",
        "MMCR v8 quest rows use unsupported GPL string return contracts",
        "MMCR v7 quest rows use unsupported GPL agent/boolean return contracts",
        "MMCR v6 quest rows lack private display callbacks",
        "MMCR v5 fixed-row quest boards are unsupported"
    ) "Stock-controller registry contract"
    Assert-ContainsAny @($runtimeSource) @(
        "EvaluateQuestBoardScalar(", "kGplIntegerResultType = 1",
        "FindPrivateIntentText(board->offerNameIntentId)",
        "FindPrivateIntentText(board->offerGoalIntentId)",
        "offerCountCallbackSymbol", "offerCount > 1",
        "presentations[0].agent = guild",
        "FindRewardStateByPrivateMode",
        "state.modeObject == modeObject",
        "g_buildProfile->getFlagModeManagerRva",
        "g_buildProfile->getSelectedFlagModeRva",
        "FindRewardStateByPrivateMode(selected)",
        "FindRegisteredRewardMode(state.record->privateMode)",
        "registered != state.modeObject",
        "registeredCursor != state.record->cursorOrdinal"
    ) "Private Fl00 live-context and registry identity contract"
    foreach ($unsupportedQuestResultPath in @(
        "EvaluateQuestBoardBoolean", "EvaluateQuestBoardAgent",
        "EvaluateQuestBoardString", "g_questBoardBooleanEvaluator",
        "g_questBoardAgentEvaluator", "g_questBoardStringEvaluator"
    )) {
        if ($runtimeSource.Contains($unsupportedQuestResultPath)) {
            throw "Unsupported quest-board GPL result path remains: $unsupportedQuestResultPath"
        }
    }
    if ($runtimeSource.Contains("Quest list row-query:")) {
        throw "Quest-board steady-state row polling still writes production logs."
    }
    $questPopulateSpan = Get-SourceSpan $runtimeSource `
        "void __fastcall QuestBoardPopulate" `
        "ControllerEvent g_stockQuestBoardEvent"
    Assert-Ordered $questPopulateSpan @(
        "!g_questBoardPopulationRequested) return;",
        "Quest list population:"
    ) "Quest-board revision-gated diagnostics"
    Assert-ContainsAny @($capabilitySource, $capabilityHeader) @(
        "kManifestVersion = 1", "kMaximumCapabilityCount = 64",
        "kMaximumCapabilityBytes = 128", "kMaximumManifestBytes = 64u * 1024u",
        "ParseManifest", "capability names are not strictly increasing",
        "capability manifest contains trailing bytes", "capability is not supported by this runtime",
        'expanded-building-slots.cg-prefix', 'freestyle-cam-rebind.v1',
        'private-activity-text-registry.v1', 'generic-visitor-lists.v1',
        'stock.name-generator.v1', 'stock.ap78-enchantment-row.v1',
        'stock.controller-recipes.v1'
    ) "Runtime capability manifest contract"

    foreach ($legacyCapability in @(
        "alchemist.cgbrewing-secondary-controller",
        "alchemist.ap78-private-oil-rows",
        "alchemist.nm18-name-generator", "phantom.nm19-name-generator"
    )) {
        if ($runtimeSource.Contains($legacyCapability) -or
            $capabilitySource.Contains($legacyCapability) -or
            $capabilityHeader.Contains($legacyCapability)) {
            throw "Input-only legacy capability remains native: $legacyCapability"
        }
    }

    Assert-ContainsAny @($runtimeSource, $controllerSource, $controllerHeader) @(
        '"public-1.5.2.24"', '"beta2-1.5.2.28"',
        "SelectMajestyBuildProfile", "ValidateMajestyBuildProfile",
        "LoadRuntimeCapabilityManifest", "LoadRuntimeFeatureRegistry",
        "LoadStockControllerRegistry", "PrepareStockControllerRuntimeRecords",
        "MAJESTY_MOD_MANAGER_CONTROLLERS", "ResolvePrivateResearchDescriptor",
        "RegisterPrivateResearchDescriptors", "BuildPrivateSpellDescriptor",
        "ResolvePrivateSpellDescriptor", "HandleTimedRageAction",
        "HandleRageCommandAction", "HandleSovereignTargetAction",
        "ResolvePendingSovereignCursor", "ResolvePrivateSovereignExecutorMode",
        "ResolvePrivateSovereignUnit", "ResearchCompletionBridge",
        "GameUpdateRefreshBridge", "StockRageOfKrolmCount()",
        "StockCurrentPlayerGold()", "kStockUnaffordableGoldCost",
        "callbackSymbol.c_str()", "completionText.c_str()",
        "MajestyControllerLifecycle::RegisterManagedVtable",
        "bool RegisterPrivateStockNameGenerator",
        "A requested private name generator could not be registered",
        "StopUnsafeManagerRuntimeLaunch", "SignalManagerRuntimeReady"
    ) "Generic native runtime contract"

    foreach ($forbidden in @(
        "CGAL", "CGBR", "Alchemist", "Weapon Oil", "Phoenix", "Vigor",
        "Arcane", "Philosopher", "Laboratory", "Brewing", "Invigorating",
        "Reagent", "Alchemist_DoInvigoratingElixer", "Alchemist_Arcane_Infusion"
    )) {
        if ($runtimeSource.IndexOf($forbidden, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            throw "Package-specific controller data remains native: $forbidden"
        }
    }
    foreach ($forbidden in @("SetTimer", "CreateTimerQueue", "RunThread", "MessageBoxA")) {
        if ($runtimeSource.Contains($forbidden)) {
            throw "Non-stock controller lifecycle remains native: $forbidden"
        }
    }

    $initializeStart = $runtimeSource.IndexOf("DWORD WINAPI InitializeRuntime(void*)")
    $initializeEnd = $runtimeSource.IndexOf("}  // namespace", $initializeStart)
    if ($initializeStart -lt 0 -or $initializeEnd -le $initializeStart) {
        throw "Runtime initialization lifecycle is missing."
    }
    $initialize = $runtimeSource.Substring($initializeStart, $initializeEnd - $initializeStart)
    if (-not $initialize.Contains("requestedStockControllerRecipes != stockControllerRecipes")) {
        throw "MMCP and MMCR are not cross-validated exactly."
    }
    $readySignal = $initialize.IndexOf("SignalManagerRuntimeReady()")
    $windowHook = $initialize.IndexOf("InstallWindowProcedureHook()")
    if ($readySignal -lt 0 -or $windowHook -le $readySignal) {
        throw "Manager readiness must precede only the stock-window-dependent hook."
    }
    if ($initialize.IndexOf("if (!SignalManagerRuntimeReady())") -lt 0) {
        throw "A valid empty manager launch cannot release its suspended launcher."
    }
    foreach ($requiredPreWindowInstall in @(
        "InstallPrivateIntentTextResolver()", "InstallFreestyleCamRuntime(",
        "InstallCustomGuildFactoryFallback()", "InstallPrivateNameGenerators()",
        "ValidateStockResearchRoute()", "InstallPrivateResearchDescriptorRegistry()",
        "InstallResearchCompletionBridge()", "InstallResearchCompletionNameClone()",
        "InstallPrivateSpellDescriptorResolver()", "InstallPrivateSovereignSpellRoute()",
        "InstallPrivateRageRoute()", "InstallDialogCreationHook()",
        "InstallDialogFactoryTrace()", "InstallSecondaryControllerHook()",
        "InstallQuestBoardRowPresentation()",
        "InstallGameUpdateRefreshBridge()", "InstallPrivateEnchantmentRows()"
    )) {
        $position = $initialize.IndexOf($requiredPreWindowInstall)
        if ($position -lt 0 -or $position -ge $readySignal) {
            throw "Required static install no longer completes before manager readiness: $requiredPreWindowInstall"
        }
    }
    $ap10ControllerBlocks = (Get-CppGuardBlocks -Source $initialize -Condition "ap10Ap69ControllerRecipes") -join "`n"
    foreach ($install in @(
        "ValidateStockResearchRoute()", "InstallPrivateResearchDescriptorRegistry()",
        "InstallResearchCompletionBridge()", "InstallResearchCompletionNameClone()",
        "InstallPrivateSpellDescriptorResolver()", "InstallPrivateSovereignSpellRoute()",
        "InstallPrivateRageRoute()", "InstallGameUpdateRefreshBridge()"
    )) {
        if (-not $ap10ControllerBlocks.Contains($install)) {
            throw "AP10/AP69 controller install is not gated by its MMCR records: $install"
        }
    }
    $controllerBlocks = (Get-CppGuardBlocks -Source $initialize -Condition "stockControllerRecipes") -join "`n"
    foreach ($install in @(
        "InstallDialogCreationHook()", "InstallDialogFactoryTrace()",
        "InstallSecondaryControllerHook()", "InstallWindowProcedureHook()"
    )) {
        if (-not $controllerBlocks.Contains($install)) {
            throw "Shared controller install is not gated by nonempty MMCR: $install"
        }
    }
    $capabilityGates = @(
        @{ Condition = "privateActivityText"; Calls = @(
            "LoadPrivateIntentRegistry()") },
        @{ Condition = "privateIntentResolver"; Calls = @(
            "ValidatePrivateIntentTextProfile()",
            "InstallPrivateIntentTextResolver()") },
        @{ Condition = "privateQuestRows"; Calls = @(
            "InstallQuestBoardRowPresentation()") },
        @{ Condition = "freestyleCam"; Calls = @("InstallFreestyleCamRuntime(") },
        @{ Condition = "expandedBuildingSlots"; Calls = @(
            "InstallCustomGuildFactoryFallback()") },
        @{ Condition = "privateNameGenerators"; Calls = @(
            "InstallPrivateNameGenerators()") },
        @{ Condition = "privateEnchantmentRows"; Calls = @(
            "InstallPrivateEnchantmentRows()") },
        @{ Condition = "ap10Ap69ControllerRecipes"; Calls = @(
            "ValidateStockResearchRoute()", "InstallPrivateResearchDescriptorRegistry()",
            "InstallResearchCompletionBridge()", "InstallResearchCompletionNameClone()",
            "InstallPrivateSpellDescriptorResolver()", "InstallPrivateSovereignSpellRoute()",
            "InstallPrivateRageRoute()", "InstallGameUpdateRefreshBridge()") },
        @{ Condition = "stockControllerRecipes"; Calls = @(
            "InstallDialogCreationHook()",
            "InstallDialogFactoryTrace()", "InstallSecondaryControllerHook()",
            "InstallWindowProcedureHook()") },
        @{ Condition = "privateRewardFlagRecipes"; Calls = @(
            "InstallPrivateRewardFlagModeRegistry()") }
    )
    foreach ($gate in $capabilityGates) {
        $guarded = (Get-CppGuardBlocks `
            -Source $initialize -Condition $gate.Condition) -join "`n"
        if ([string]::IsNullOrEmpty($guarded)) {
            throw "Runtime capability guard is missing: $($gate.Condition)"
        }
        foreach ($call in $gate.Calls) {
            $allCount = ([regex]::Matches(
                $initialize, [regex]::Escape($call))).Count
            $guardedCount = ([regex]::Matches(
                $guarded, [regex]::Escape($call))).Count
            if ($allCount -ne 1 -or $guardedCount -ne 1) {
                throw "Runtime call is not exclusively gated by $($gate.Condition): $call"
            }
        }
    }
    foreach ($install in @(
        "InstallFreestyleCamRuntime", "InstallCustomGuildFactoryFallback",
        "InstallPrivateNameGenerators", "ValidateStockResearchRoute",
        "InstallPrivateResearchDescriptorRegistry", "InstallResearchCompletionBridge",
        "InstallResearchCompletionNameClone", "InstallPrivateSpellDescriptorResolver",
        "InstallPrivateSovereignSpellRoute", "InstallPrivateRageRoute",
        "InstallDialogCreationHook", "InstallDialogFactoryTrace",
        "InstallSecondaryControllerHook", "InstallGameUpdateRefreshBridge",
        "InstallPrivateRewardFlagModeRegistry", "InstallPrivateEnchantmentRows",
        "InstallQuestBoardRowPresentation", "InstallWindowProcedureHook"
    )) {
        $pattern = "RequireManagerRuntimeInstall\(\s*" + [regex]::Escape($install) + "\("
        if (-not [regex]::IsMatch($initialize, $pattern)) {
            throw "Manager launch does not fail closed for required install: $install"
        }
    }
    $absent = (Get-CppGuardBlocks -Source $initialize -Condition "capabilityManifest == CapabilityManifestState::Absent") -join "`n"
    if (-not $absent.Contains("return 0;")) {
        throw "Injection without MMCP does not leave optional hooks untouched."
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

    if ($runtimeSource.Contains("ResolveResearchDescriptorHook")) {
        throw "Private AP99 registration reverted to an incomplete call-site resolver hook."
    }
    if ($runtimeSource -match
        'if\s*\(g_privateResearchDescriptorsRegistered\)\s*\{\s*return true;') {
        throw "Private AP99 registration is no longer revalidated after a stock registry rebuild."
    }

    $descriptorStart = $runtimeSource.IndexOf("bool InstallPrivateResearchDescriptorRegistry()")
    $descriptorEnd = $runtimeSource.IndexOf("bool InstallResearchCompletionBridge()", $descriptorStart)
    if ($descriptorStart -lt 0 -or $descriptorEnd -le $descriptorStart) {
        throw "AP99 private registry installer is missing."
    }
    $descriptorInstall = $runtimeSource.Substring($descriptorStart, $descriptorEnd - $descriptorStart)
    foreach ($patchApi in @("VirtualAlloc", "VirtualProtect", "FlushInstructionCache")) {
        if ($descriptorInstall.Contains($patchApi)) {
            throw "AP99 registration patches its stock resolver: $patchApi"
        }
    }
    Assert-ContainsAny @($runtimeSource) @(
        "dispatchSlot[-1] != 0x00002009u", "dispatchSlot[1] != 0x0000200Bu",
        "g_stockResearchCompletion", "&ResearchCompletionBridge",
        "CaptureBuildingActivity(context)", "RestoreBuildingActivity(context, liveActivity)",
        "CaptureSubmittedResearch(activityBeforeUpdate)"
    ) "Stock AP99 completion lifecycle"

    $childSetup = Get-SourceSpan $runtimeSource `
        "void __fastcall SecondaryPanelControllerSetup(" `
        "int __fastcall SecondaryPanelControllerControl("
    Assert-Ordered $childSetup @(
        "g_stockAp69Setup(controller);",
        "RegisterPrivateResearchDescriptors()",
        "BuildPrivateSpellDescriptor(&state)",
        "RefreshPrivateActionRows(value, true);",
        "RefreshTimedRageRows(value);",
        "RefreshPrivateResearchRows(value);",
        "UpdateSecondaryPanelPresentation(value);"
    ) "AP69 child setup"
    $childEvent = Get-SourceSpan $runtimeSource `
        "void __fastcall SecondaryPanelControllerEvent(" `
        "void ClearSecondaryPanelControllerOwnedState()"
    Assert-Ordered $childEvent @(
        "g_stockAp69Event(controller, argument1, argument2, argument3, argument4);",
        "UpdateSecondaryPanelPresentation(",
        "if (stockResearchRefresh)",
        "RefreshTimedRageRows(value);",
        "RefreshPrivateResearchRows(value);",
        "RefreshPrivateActionRows(value, true);"
    ) "AP69 child event refresh"
    $parentSetup = Get-SourceSpan $runtimeSource `
        "void __fastcall ParentPanelControllerSetup(" `
        "void __fastcall ParentPanelControllerActivity("
    Assert-Ordered $parentSetup @(
        "g_stockParentSetup(controller);",
        "getPanelContext(controller)",
        "ApplyUpgradeResearchGate("
    ) "AP10 parent setup"
    $parentActivity = Get-SourceSpan $runtimeSource `
        "void __fastcall ParentPanelControllerActivity(" `
        "void __fastcall ParentPanelControllerEvent("
    Assert-Ordered $parentActivity @(
        "g_stockParentActivity(controller);",
        "ApplyUpgradeResearchGate("
    ) "AP10 parent activity refresh"
    $parentEvent = Get-SourceSpan $runtimeSource `
        "void __fastcall ParentPanelControllerEvent(" `
        "void __cdecl ParentPanelControllerDestroyed("
    Assert-Ordered $parentEvent @(
        "g_stockParentEvent(",
        "ApplyUpgradeResearchGate(",
        "getPanelContext(controller)"
    ) "AP10 parent event refresh"
    $childClear = Get-SourceSpan $runtimeSource `
        "void ClearSecondaryPanelControllerOwnedState()" `
        "void __cdecl SecondaryPanelControllerDestroyed("
    Assert-ContainsAny @($childClear) @(
        "g_secondaryPanelHandle", "g_secondaryPanelActive",
        "g_captureChildController", "g_pendingSovereignAction = nullptr",
        "g_pendingSovereignBuilding", "g_activePanelRecord = nullptr"
    ) "AP69 child teardown ownership"
    $parentClear = Get-SourceSpan $runtimeSource `
        "void __cdecl ParentPanelControllerDestroyed(" `
        "bool InstallParentPanelControllerVtable("
    Assert-ContainsAny @($parentClear) @(
        "g_captureParentController", "g_secondaryPanelArmed",
        "g_ap10ControllerContext", "g_parentPanelRecord = nullptr",
        "g_parentOccupantPanel = nullptr", "g_parentRewardPanelRecord = nullptr"
    ) "AP10 parent teardown ownership"
    foreach ($childOwned in @("g_childController", "g_activePanelRecord = nullptr", "ClearSecondaryPanelControllerOwnedState();")) {
        if ($parentClear.Contains($childOwned)) {
            throw "Parent teardown must not invalidate a surviving child: $childOwned"
        }
    }
    $captureController = Get-SourceSpan $runtimeSource `
        'extern "C" void __stdcall CaptureSecondaryController(' `
        "void DismissSecondaryPanel()"
    Assert-ContainsAny @($captureController) @(
        "if (controller == 0)",
        "A resolved parent dialog returned no stock controller",
        "A resolved secondary dialog returned no stock controller",
        "ClearSecondaryPanelControllerOwnedState();",
        "StopUnsafeManagerRuntimeLaunch("
    ) "Matched panel creation failure boundary"
    foreach ($forbiddenCaptureCallback in @(
        "RefreshQuestBoardParentPresentation(",
        "QueryQuestBoard("
    )) {
        if ($captureController.Contains($forbiddenCaptureCallback)) {
            throw "Controller capture must not execute package GPL: $forbiddenCaptureCallback"
        }
    }
    $dialogCreation = Get-SourceSpan $runtimeSource `
        'extern "C" void __stdcall ResolveDialogCreationRequest(' `
        "__declspec(naked) void DialogCreationHook()"
    Assert-ContainsAny @($dialogCreation) @(
        "const auto* requestedChild =",
        "InterlockedExchange(&g_childController, 0);",
        "ClearSecondaryPanelControllerOwnedState();",
        "g_parentPanelRecord = requestedParent;",
        "g_parentOccupantPanel = occupantParent;"
    ) "Dialog replacement ownership boundary"

    $questChildInstall = Get-SourceSpan $runtimeSource `
        "bool InstallQuestBoardChildVtable(std::uint32_t controller) {" `
        "struct OccupantParentClass"
    Assert-ContainsAny @($questChildInstall) @(
        "table[8] = reinterpret_cast<void*>(&QuestBoardEvent);",
        "table[11] = reinterpret_cast<void*>(&QuestBoardPopulate);"
    ) "MX05 quest lifecycle hooks"
    foreach ($forbiddenQuestChildOverride in @(
        "table[3] =", "table[10] =", "table[14] ="
    )) {
        if ($questChildInstall.Contains($forbiddenQuestChildOverride)) {
            throw "Quest-board MX05 child replaces a stock virtual: $forbiddenQuestChildOverride"
        }
    }
    Assert-ContainsAny @($runtimeSource) @(
        "Quest list callback resolve:",
        "the package offer-count callback did not return an integer"
    ) "Quest-board scalar callback diagnostics"
    $occupantParentInstall = Get-SourceSpan $runtimeSource `
        "bool InstallOccupantParentVtable(std::uint32_t controller) {" `
        "bool InstallOccupantChildVtable(std::uint32_t controller) {"
    Assert-ContainsAny @($occupantParentInstall) @(
        "g_parentOccupantPanel->parentControllerBase",
        "declaredBase == kAp08DialogId",
        "kAp08VtableEntries"
    ) "Declared AP08 occupant parent boundary"
    $occupantChildInstall = Get-SourceSpan $runtimeSource `
        "bool InstallOccupantChildVtable(std::uint32_t controller) {" `
        "bool InstallRewardPanelControllerVtable(std::uint32_t controller) {"
    Assert-ContainsAny @($occupantChildInstall) @(
        "std::memcpy(table, stock, sizeof(table));",
        "RegisterManagedVtable(table, stock, 15"
    ) "Unchanged stock MX05 occupant child lifecycle"
    foreach ($forbiddenOccupantChildOverride in @(
        "table[1] =", "table[3] =", "table[8] =", "table[11] =", "table[14] ="
    )) {
        if ($occupantChildInstall.Contains($forbiddenOccupantChildOverride)) {
            throw "Occupant-action MX05 child replaces a stock virtual: $forbiddenOccupantChildOverride"
        }
    }
    $questEvent = Get-SourceSpan $runtimeSource `
        "void __fastcall QuestBoardEvent(" `
        "bool InstallQuestBoardChildVtable("
    Assert-Ordered $questEvent @(
        "g_stockQuestBoardEvent(",
        "if (a3 == 0x09435358u)",
        "return;",
        "if (g_activeQuestRevision == static_cast<int>(revision)) return;",
        "g_questBoardPopulationRequested = true;",
        "g_stockQuestBoardRefresh(controller);"
    ) "MX05 stock XSCX and revision refresh"
    foreach ($forbiddenQuestEventWrite in @(
        "SetControllerControlInteger(", "SendControllerMessage("
    )) {
        if ($questEvent.Contains($forbiddenQuestEventWrite)) {
            throw "MX05 quest event performs a non-stock child write: $forbiddenQuestEventWrite"
        }
    }
    $questPopulation = Get-SourceSpan $runtimeSource `
        "void __fastcall QuestBoardPopulate(" `
        "ControllerEvent g_stockQuestBoardEvent"
    Assert-ContainsAny @($questPopulation) @(
        "!g_questBoardPopulationRequested) return;",
        "FaultQuestBoardPresentation(",
        "package offer-count callback did not return an integer",
        "package offer count exceeded the proven one-row contract",
        "return;"
    ) "Fault-contained quest-board presentation"
    if ($questPopulation.Contains("StopUnsafeManagerRuntimeLaunch(")) {
        throw "Package quest-row data failures must not become runtime-install failures."
    }
    $questRowName = Get-SourceSpan $runtimeSource `
        "void* __cdecl QuestBoardRowNameFormatter(" `
        "int __fastcall QuestBoardRowIntentAttribute("
    Assert-Ordered $questRowName @(
        "g_stockQuestRowNameFormatter(destination, agent, stockStyle);",
        "g_privateIntentStringAssign(destination, &view);"
    ) "Stock-constructed private quest-row name lifecycle"

    $researchBegin = Get-SourceSpan $runtimeSource `
        "int BeginPrivateResearch(" `
        "int HandleRageCommandAction("
    Assert-Ordered $researchBegin @(
        "CaptureBuildingActivity(context)", "ClearBuildingActivity(context);",
        "canSubmitResearch(", "g_researchOwner.pending = true;",
        "submitResearchCommand(commandOwner, context, row.actionControlId);",
        "CaptureSubmittedResearch(liveActivity)",
        "RestoreBuildingActivity(context, liveActivity);"
    ) "AP99 private submission"
    $researchCapture = Get-SourceSpan $runtimeSource `
        "bool CaptureSubmittedResearch(" `
        "void StageResearchForStockCompletion()"
    Assert-Ordered $researchCapture @(
        "CaptureBuildingActivity(g_researchOwner.context)",
        "RestoreBuildingActivity(", "g_researchOwner.pending = false;",
        "g_researchOwner.active = true;"
    ) "AP99 queued tuple capture"
    $researchCompletion = Get-SourceSpan $runtimeSource `
        "void __cdecl ResearchCompletionBridge(" `
        "void __fastcall GameUpdateRefreshBridge("
    Assert-Ordered $researchCompletion @(
        "CaptureBuildingActivity(context)", "StageResearchForStockCompletion();",
        "g_stockResearchCompletion(", "CaptureBuildingActivity(context)",
        "RestoreBuildingActivity(context, liveActivity);", "g_researchOwner = {};"
    ) "AP99 event 0x2009 completion handoff"
    $researchRegistration = Get-SourceSpan $runtimeSource `
        "bool RegisterPrivateResearchDescriptors()" `
        "bool InstallPrivateResearchDescriptorRegistry()"
    Assert-Ordered $researchRegistration @(
        "if (allRegistered) return true;", "if (!allAbsent)",
        "state.descriptor = nullptr;", "ResolvePrivateResearchDescriptor(&state)",
        "findOrInsert(", "*slot = state.descriptor;",
        "resolveResearchDescriptor(state.record->actionControlId)"
    ) "AP99 registry rebuild/re-registration"

    $timedHandler = Get-SourceSpan $runtimeSource `
        "int HandleTimedRageAction(" `
        "int BeginPrivateResearch("
    Assert-Ordered $timedHandler @(
        "g_timedRageActive", "StockRageOfKrolmCount()",
        "g_pendingRageHandle", "ResourceStock(", "StockCurrentPlayerGold()",
        "SubmitPrivateRageCommand(action.callbackSymbol.c_str())",
        "g_activeTimedRageAction = &action;", "g_timedRageStartedAt = SimulationClock();",
        "InterlockedExchange(&g_timedRageActive, 1);"
    ) "AP24 timed action submission"
    $rageSubmission = Get-SourceSpan $runtimeSource `
        "bool SubmitPrivateRageCommand(" `
        "int HandleTimedRageAction("
    Assert-Ordered $rageSubmission @(
        "getCommandMetadata(context, &metadata);",
        "InterlockedExchange(&g_pendingRageHandle",
        "submitBuildingCommand("
    ) "AP24 Rage command metadata"
    $timedPresentation = Get-SourceSpan $runtimeSource `
        "void UpdateSecondaryPanelPresentation(" `
        "bool CaptureSubmittedResearch("
    Assert-ContainsAny @($timedPresentation) @(
        "elapsed >= action.durationMs", "InterlockedExchange(&g_timedRageActive, 0)",
        "g_activeTimedRageAction = nullptr", "StockRageOfKrolmCount() != 0",
        "action.resourceCost", "g_pendingRageHandle"
    ) "AP24 timed UI/effector ownership"
    $rageDispatch = Get-SourceSpan $runtimeSource `
        "__declspec(naked) void RageCommandDispatchHook()" `
        "bool InstallPrivateRageRoute()"
    Assert-ContainsAny @($rageDispatch) @(
        "cmp ecx, dword ptr [g_pendingRageHandle]",
        "SelectPrivateRageCallback", "g_pendingTimedRageAction->callbackSymbol.c_str()",
        "g_pendingRageCommandAction->callbackSymbol.c_str()",
        "mov dword ptr [g_pendingRageHandle], 0",
        "push dword ptr [g_privateRageCallback]",
        "jmp dword ptr [g_rageGplConstructionResume]"
    ) "Exact-handle Rage GPL callback dispatch"

    $sovereignHandler = Get-SourceSpan $runtimeSource `
        "int HandleSovereignTargetAction(" `
        "const std::uint32_t* ResolvePrivateResearchDescriptor("
    Assert-Ordered $sovereignHandler @(
        "g_pendingSovereignBuilding", "g_pendingSovereignAction = &action;",
        "beginSovereignTarget(action.privateControlId);"
    ) "Sovereign target session publication"
    $sovereignSubmit = Get-SourceSpan $runtimeSource `
        'extern "C" void __cdecl SubmitPrivateSovereignCommand(' `
        'extern "C" std::uint32_t __stdcall ResolvePrivateSovereignExecutorMode('
    Assert-ContainsAny @($sovereignSubmit) @(
        "mode == action->stockTargetMode", "cost = kStockUnaffordableGoldCost;",
        "mode = action->privateMode;", "target = building;", "cost = 0;",
        "submit(mode, player, x, y, target, cost);"
    ) "Sovereign stock commit/repeat route"
    foreach ($forbiddenCancel in @(
        "CancelSovereignTargetMode", "CancelSovereignTargetWithoutSelection",
        "g_pendingSovereignAction = nullptr"
    )) {
        if ($sovereignSubmit.Contains($forbiddenCancel)) {
            throw "Sovereign commit incorrectly cancels repeat-cast state: $forbiddenCancel"
        }
    }
    $sovereignExecution = Get-SourceSpan $runtimeSource `
        'extern "C" std::uint32_t __stdcall ResolvePrivateSovereignExecutorMode(' `
        "bool InstallPrivateSovereignSpellRoute()"
    Assert-ContainsAny @($sovereignExecution) @(
        "FindSovereignByPrivateMode(mode)", "action->stockExecutorMode",
        "action->privateUnitId", "&g_executingSovereignUnit, 0",
        "PublicSovereignExecutorHook", "Beta2SovereignExecutorHook",
        "PublicSovereignConstructionHook", "Beta2SovereignConstructionHook"
    ) "Sovereign executor/unit construction ownership"
    $windowProcedure = Get-SourceSpan $runtimeSource `
        "LRESULT CALLBACK RuntimeWindowProcedure(" `
        "BOOL CALLBACK FindRuntimeWindow("
    Assert-Ordered $windowProcedure @(
        "CallWindowProcA(", "message == WM_RBUTTONDOWN",
        "g_pendingSovereignAction = nullptr", "g_pendingSovereignBuilding",
        "DismissSecondaryPanel();"
    ) "Stock right-click cancel boundary"

    Assert-ContainsAny @($freestyleSource) @(
        "struct FreestyleCamProfile", '"public-1.5.2.24"', '"beta2-1.5.2.28"',
        "kPublicFreestyleProfile", "kBeta2FreestyleProfile", "AcquireImage",
        "EnsureLiveRegistry", "PreflightProfile", "RollBackPatches",
        "WriteReleaseVtable8Patch", "kMajestyComVtableSpan = 0x00400000",
        "IsStockRenderWrapper", "HasStockVtableMethod",
        "stockCodeRva = g_profile->wrapperAssignRva", "IsGameCode(method18)",
        "ClearRegistryCache();", "__finally", "previous == incoming",
        '"upstream-parity"', "installed stock IMAG rebind and dead-wrapper teardown guards"
    ) "Freestyle runtime contract"
    foreach ($guard in @(
        @{ Name = "SafeReleasePointer"; Next = "void __stdcall SafeReleaseVtable8(" },
        @{ Name = "SafeReleaseVtable8"; Next = "__declspec(naked) void HandleUseHook(" }
    )) {
        $start = $freestyleSource.IndexOf("void __stdcall $($guard.Name)(")
        $end = $freestyleSource.IndexOf($guard.Next, $start)
        if ($start -lt 0 -or $end -le $start) {
            throw "The upstream teardown guard is missing: $($guard.Name)"
        }
        $body = $freestyleSource.Substring($start, $end - $start)
        if (-not $body.Contains("ClearRegistryCache();") -or
            $body.Contains("if (pointer != 0)")) {
            throw "$($guard.Name) no longer clears the registry cache for every non-live pointer."
        }
    }
    foreach ($forbidden in @("Sleep(2000)", "version.dll", "Suppress registry destructor", "detour_wrap_use")) {
        if ($freestyleSource.Contains($forbidden)) {
            throw "Rejected sidecar behavior remains integrated: $forbidden"
        }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "licenses\FREESTYLE-CAM-SIDECAR.txt") -PathType Leaf)) {
        throw "The freestyle-cam-sidecar MIT notice is missing."
    }
    $runtimeDllText = [Text.Encoding]::ASCII.GetString(
        [IO.File]::ReadAllBytes((Join-Path $output "MajestyBuildingRuntime.dll")))
    if (-not $runtimeDllText.Contains("upstream-parity")) {
        throw "Default runtime DLL omits the validated upstream assignment mode."
    }

    Write-Host "Majesty Mod Manager native runtime tests passed."
}
finally {
    if (Test-Path -LiteralPath $output) {
        Remove-Item -LiteralPath $output -Recurse -Force
    }
}
