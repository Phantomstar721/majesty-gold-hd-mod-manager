#include "../runtime/RegistrationDiagnostic.h"
#include <cassert>
#include <string>
#include <vector>
static std::vector<std::string> rows;
static void Capture(const char* row) { rows.emplace_back(row); }
int main() {
    for(unsigned i=0;i<10;++i) {
        RegistrationDiagnostic d(&Capture);
        d.Begin(0,1,123,456);
        for(unsigned j=0;j<1000;++j)d.Stage("intermediate",j);
        if(i==1)d.Accept("reregistered");
        else d.Stage("startup-world-present",0x123,0x456,0x789);
    }
#if defined(MAJESTY_REGISTRATION_DIAGNOSTIC)
    assert(rows.size()==16);
    assert(rows[0].find("stage=entry a=00000000 b=00000001 c=0000007b result=000001c8")!=std::string::npos);
    assert(rows[1].find("stage=startup-world-present a=00000123 b=00000456 c=00000789 result=00000000")!=std::string::npos);
    assert(rows[3].find("stage=reregistered")!=std::string::npos);
    assert(rows[3].find("result=00000001")!=std::string::npos);
    assert(rows.back().find("attempt=8")!=std::string::npos);
#else
    assert(rows.empty());
#endif
}
