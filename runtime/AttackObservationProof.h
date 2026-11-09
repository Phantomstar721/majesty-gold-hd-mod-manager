#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <set>
#include <vector>

namespace MajestyAttackObservation {
struct PackageProof {
    bool scoped{};
    std::string featureKey, apiPrefix, actor, action, projectile, releaseCallback;
    std::vector<std::array<unsigned char,32>> digests;
    std::set<std::string> protectedNames;
    int Find(const unsigned char* digest) const;
};
bool ParsePackageProof(const unsigned char*, std::size_t, PackageProof&);

// Observes stock loader calls, never changes their dispatch or precedence.
// Readiness requires successful baseline completion and the actual composed
// outputs (shared and one dataset, in either order). Independently parsed
// non-overlapping archives do not invalidate it. Opaque/conflicting loads fail.
class LoadProof {
public:
    explicit LoadProof(bool scoped=false):scoped_(scoped) {}
    bool Begin(int index);
    bool Complete(int index, bool success);
    bool Ready() const { return !fault_ && stack_.empty() && completed_ == 6 &&
        (finished_ & (1u<<6)) && (!scoped_ || (finished_ & ((1u<<7)|(1u<<8)))); }
    bool Faulted() const { return fault_; }
    struct State { unsigned started,completed,finished,depth; int top; bool fault,scoped; };
    State DiagnosticState() const {
        return {started_,completed_,finished_,static_cast<unsigned>(stack_.size()),
                stack_.empty()?-99:stack_.back(),fault_,scoped_};
    }
private:
    std::vector<int> stack_;
    unsigned started_{}, completed_{};
    unsigned finished_{};
    bool fault_{};
    bool scoped_{};
};
}
