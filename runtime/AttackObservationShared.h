#pragma once
#include "AttackObservation.h"
// Internal access to the existing loaded-BCD/world observer. No new GPL names,
// alternate world tracker or changed shot-token meanings are introduced here.
namespace MajestyAttackObservation {
const Memory& SharedMemory();
bool SharedProofMatches(const unsigned char* digest);
bool SharedCurrentIdentity(Address unit,std::uint32_t id,Address world,Address description);
bool SharedIdle(Address unit,std::uint32_t id,Address description);
bool SharedDecisionContext();
void SharedDiagnosticLine(const char*);
const char* SharedIdentityFailure();
void* SharedArgument(void* arguments,unsigned index);
// Raw frame slots include the implicit result at zero; for stock scheduler hooks.
void* SharedFrameArgument(void* arguments,unsigned index);
Address SharedFrameAgent(void* arguments,unsigned index);
Address SharedAgent(void* arguments,unsigned index);
int* SharedInteger(void* arguments,unsigned index);
}
