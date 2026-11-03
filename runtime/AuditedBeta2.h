#pragma once
#include "MajestyBuildId.h"
namespace MajestyCheckedPlacement {
// Guarded three-build bodies, fixed image base and no attached/current world.
// Internal startup evidence; no caller-supplied assertion can replace it.
bool AuditedStartup(MajestyBuildId);
}
