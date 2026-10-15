#pragma once
#include <atomic>
#include <cstdio>

// Registration only: two bounded records per attempt, never a gameplay trace.
class RegistrationDiagnostic {
public:
    explicit RegistrationDiagnostic(void (*writer)(const char*)) : writer_(writer) {
#if defined(MAJESTY_REGISTRATION_DIAGNOSTIC)
        static std::atomic<unsigned> attempts{0};
        attempt_=++attempts;
#endif
    }
    void Stage(const char* name,unsigned a=0,unsigned b=0,unsigned c=0) {
        stage_=name; a_=a; b_=b; c_=c;
    }
    void Begin(unsigned build,unsigned flags,unsigned thread,unsigned owner) {
        Stage("entry",build,flags,thread); Emit(owner);
    }
    bool Accept(const char* name) { Stage(name); success_=true; return true; }
    ~RegistrationDiagnostic() { Emit(success_?1u:0u); }
private:
    void Emit(unsigned result) {
#if defined(MAJESTY_REGISTRATION_DIAGNOSTIC)
        if(writer_ && attempt_<=8) {
            char line[256]{};
            std::snprintf(line,sizeof(line),"RegistrationDiagnostic/v1 attempt=%u stage=%s a=%08x b=%08x c=%08x result=%08x",
                attempt_,stage_,a_,b_,c_,result);
            writer_(line);
        }
#else
        (void)result;
#endif
    }
    void (*writer_)(const char*);
    unsigned attempt_=0,a_=0,b_=0,c_=0;
    const char* stage_="aborted";
    bool success_=false;
};
