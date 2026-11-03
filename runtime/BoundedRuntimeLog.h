#pragma once
#include <windows.h>
#include <cstdio>
#include <cstring>

// Fixed storage, no unit queries, background worker, heap growth or polling.
namespace MajestySupportLog {
constexpr unsigned Rows=128, Width=1024, LogLimit=1024*1024, FaultLimit=256*1024;
static SRWLOCK lock=SRWLOCK_INIT;
static char recent[Rows][Width]{};
static unsigned cursor=0, count=0;
static bool captured=false;

inline void Rotate(const char* path) {
    char first[MAX_PATH]{},second[MAX_PATH]{};
    std::snprintf(first,sizeof(first),"%s.1",path);
    std::snprintf(second,sizeof(second),"%s.2",path);
    MoveFileExA(first,second,MOVEFILE_REPLACE_EXISTING);
    MoveFileExA(path,first,MOVEFILE_REPLACE_EXISTING);
}
inline void Append(const char* path,const char* line,unsigned limit,bool rotate) {
    WIN32_FILE_ATTRIBUTE_DATA data{};
    if(GetFileAttributesExA(path,GetFileExInfoStandard,&data) &&
       (data.nFileSizeHigh || data.nFileSizeLow+std::strlen(line)+2>limit)) {
        if(!rotate)return;
        Rotate(path);
        // A sharing/access failure must not turn the cap into unlimited growth.
        if(GetFileAttributesExA(path,GetFileExInfoStandard,&data) &&
           (data.nFileSizeHigh || data.nFileSizeLow+std::strlen(line)+2>limit))return;
    }
    FILE* out=nullptr;
    if(!fopen_s(&out,path,"ab") && out) { std::fputs(line,out);std::fputc('\n',out);std::fclose(out); }
}
inline void Write(const char* path,const char* message,bool failure=false) {
    AcquireSRWLockExclusive(&lock);
    SYSTEMTIME now{};GetLocalTime(&now);
    char line[Width]{};
    std::snprintf(line,sizeof(line),"%04u-%02u-%02u %02u:%02u:%02u.%03u pid=%lu tid=%lu %.850s",
        now.wYear,now.wMonth,now.wDay,now.wHour,now.wMinute,now.wSecond,now.wMilliseconds,
        GetCurrentProcessId(),GetCurrentThreadId(),message?message:"");
    std::memcpy(recent[cursor],line,sizeof(line));cursor=(cursor+1)%Rows;if(count<Rows)++count;
    Append(path,line,LogLimit,true);
    const bool firstFault=message && std::strstr(message,"FirstFault/v3 reason=")==message;
    char faultPath[MAX_PATH]{};std::snprintf(faultPath,sizeof(faultPath),"%s.fault",path);
    if((failure||firstFault)&&!captured) {
        captured=true;Rotate(faultPath);
        for(unsigned i=0;i<count;++i)Append(faultPath,recent[(cursor+Rows-count+i)%Rows],FaultLimit,false);
    } else if(captured && message && (failure || std::strstr(message,"FirstFault/")==message)) {
        Append(faultPath,line,FaultLimit,false);
    }
    ReleaseSRWLockExclusive(&lock);
}
}
