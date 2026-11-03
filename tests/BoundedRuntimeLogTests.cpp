#include "../runtime/BoundedRuntimeLog.h"
#include <cassert>
#include <string>
#include <fstream>
static std::string Read(const char* path) {
    std::ifstream in(path,std::ios::binary);return {std::istreambuf_iterator<char>(in),{}};
}
int main() {
    char temporary[MAX_PATH]{},path[MAX_PATH]{};
    assert(GetTempPathA(MAX_PATH,temporary));assert(GetTempFileNameA(temporary,"mml",0,path));
    MajestySupportLog::Write(path,"prior context");
    MajestySupportLog::Write(path,"FirstFault/v3 reason=fixture");
    MajestySupportLog::Write(path,"FirstFault/v3 proof detail");
    const std::string fault=std::string(path)+".fault";
    const auto captured=Read(fault.c_str());
    assert(captured.find("prior context")!=std::string::npos);
    assert(captured.find("proof detail")!=std::string::npos);
    std::string noise(1800,'x');
    for(unsigned i=0;i<5000;++i)MajestySupportLog::Write(path,noise.c_str());
    assert(Read(fault.c_str())==captured); // rotations cannot erase first failure
    for(const char* suffix:{"",".1",".2",".fault",".fault.1",".fault.2"}) {
        auto file=std::string(path)+suffix;
        assert(Read(file.c_str()).size()<=MajestySupportLog::LogLimit);
        DeleteFileA(file.c_str());
    }
}
