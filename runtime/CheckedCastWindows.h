#pragma once
#include "CheckedCast.h"
#include "AttackObservation.h"
#include "CosmeticActionCleanup.h"
#include "CosmeticActionState.h"
namespace MajestyCheckedPlacement {
struct CastBindings {
    const MajestyAttackObservation::Memory* memory{};
    bool (*identity)(Word unit,Identity&){};
    // Same stock GPL argument accessor used by the Manager registration bridge.
    void* (*argument)(void* arguments,unsigned index){};
    Word (*agent)(void* arguments,unsigned index){};
    Word action{},actionEngine{},movementCallback{};
};
// This internal observer cannot be activated without effective loaded bindings.
// Installation itself belongs to the final exact-image/provider startup gate.
bool ConfigureCastBindings(const CastBindings&);
std::uint64_t ObservedUnitEpoch(Word unit,Word id);
StockCasts& NativeCasts();
std::uint64_t ObserveCastSubmissionStarting(Word unit,Word order);
void ObserveCastSubmit(Word unit,Word channel,Word order,Word result,std::uint64_t revision);
void ObserveCastUnlink(Word unit,Word order);
void ObserveCastRetire(Word unit);
void ResetCastBindings();
bool BeginObservedCast(const Identity&,const Identity&,Word actorProxy,Word targetProxy,const char* actionName);
void CancelObservedCast(Word actor);
bool InstallCastObservers(MajestyBuildId);
void CastBindingEpochChanged();
// Internal only; the effective package adapter supplies declared descriptors.
bool ConfigureCosmeticCleanup(const CosmeticActionState&);
bool CosmeticAvailable(Word unit);
bool BeginCosmeticAction(const Identity&,Word actorProxy,const char* actionName);
bool EnterCastOperation();
void LeaveCastOperation(bool normal);
}
