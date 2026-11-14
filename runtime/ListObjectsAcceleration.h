#pragma once
#include <cstdint>
#include "MajestyBuildId.h"

// Behaviour-preserving acceleration of stock $ListObjects: replaces only the
// per-unit filter callback that stock hands to each candidate collection's
// ForEach, with one that reaches exactly the same decision and pushes exactly
// the same result record with less work. See docs/listobjects-acceleration.md.
//
// Install() validates the selected executable profile and every guarded stock
// body before writing a single 4-byte immediate. It returns false, logs why
// and leaves the executable untouched for an unaudited build or any mismatch.
// Built with MAJESTY_LISTOBJECTS_DIFFERENTIAL, the installed callback instead
// evaluates its own decision, runs the stock callback for the real result and
// logs every disagreement (verification builds only).
namespace ListObjectsAcceleration {
bool Install(std::uintptr_t imageBase, MajestyBuildId build, void (*log)(const char*));
}
