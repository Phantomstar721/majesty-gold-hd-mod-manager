#include "CheckedNativeState.h"
#include <limits>
namespace MajestyCheckedPlacement {
namespace {
template<class T> bool Read(const StateServices& s,Word p,unsigned offset,T& out) {
    return s.memory&&p&&p<=UINT32_MAX-offset&&sizeof(T)<=UINT32_MAX-p-offset&&
        s.memory->Read(p+offset,&out,sizeof(out));
}
bool Method(const StateServices& s,Word table,unsigned slot,Word expected) {
    Word method{};return Read(s,table,slot,method)&&method==expected;
}
bool Engine(const StateServices& s,const Identity& unit,Word& engine) {
    Word type{},id{},nativeId{};
    return Read(s,unit.description,4,id)&&Read(s,unit.address,0x7C,nativeId)&&id==nativeId&&
        Read(s,unit.description,8,type)&&type>=1&&type<=5&&
        Read(s,unit.description,0x14,engine)&&engine;
}
bool Shape(const StateServices& s,Word engine,Footprint& out) {
    Word flags{},bitmap{};
    if(!Read(s,engine,0x3C,flags)||!(flags&1)||!Read(s,engine,0x2C,bitmap))return false;
    if(bitmap) {
        int width{},height{},stride{};Point offset{};Word data{};
        if(!Read(s,bitmap,0,width)||!Read(s,bitmap,4,height)||!Read(s,bitmap,8,stride)||
            !Read(s,bitmap,0xC,offset.x)||!Read(s,bitmap,0x10,offset.y)||!Read(s,bitmap,0x14,data)||
            width<1||width>129||height<1||height>129||stride<(width+7)/8||stride>32||!data)return false;
        std::vector<std::uint8_t> bytes(static_cast<std::size_t>(stride)*height);
        return s.memory->Read(data,bytes.data(),bytes.size())&&DecodeBitmap(width,height,stride,offset,bytes,out);
    }
    int left{},top{},right{},bottom{};
    return (flags&4)&&Read(s,engine,0x14,left)&&Read(s,engine,0x18,top)&&
        Read(s,engine,0x1C,right)&&Read(s,engine,0x20,bottom)&&DecodeRectangle(left,top,right,bottom,out);
}
bool NormalMovement(const StateServices& s,const Identity& actor,Word engine) {
    Word current{},normal{},kind{},pointer{},subtype{},movement{},table{},mask{};unsigned matches=0;
    if(!Read(s,actor.address,0x54,current)||!current||!Read(s,engine,0x80,mask)||
        !(mask&0x10)||(mask&0x20))return false;
    for(unsigned i=0;i<8;++i) {
        if(!Read(s,engine,0xD4+12*i,kind))return false;
        if(kind==1) {if(!Read(s,engine,0xDC+12*i,pointer))return false;normal=pointer;++matches;}
    }
    return matches==1&&current==normal&&Read(s,current,8,subtype)&&subtype==1&&
        Read(s,current,0x14,movement)&&Read(s,movement,0,table)&&s.profile&&table==s.profile->linearMovement;
}
bool Position(const StateServices& s,Word unit,Point& out) {
    // Outside-only GSUnit stores Q11 pixel coordinates; no containment or
    // interpolated/render position is substituted for the stock map position.
    int x{},y{};
    if(!Read(s,unit,0x58,x)||!Read(s,unit,0x5C,y)||x<0||y<0)return false;
    out={x>>11,y>>11};return true;
}
bool Hostile(const StateServices& s,const Identity& a,const Identity& t) {
    if(a.world!=t.world||a.player==t.player||a.player>=8||t.player>=8)return false;
    unsigned aGroups=0,tGroups=0;
    for(unsigned i=0;i<8;++i) {
        Word mask{};if(!Read(s,a.world,0x128+4*i,mask))return false;
        const bool aa=(mask&(1u<<a.player))!=0,tt=(mask&(1u<<t.player))!=0;
        if(aa&&tt)return false;if(aa)++aGroups;if(tt)++tGroups;
    }
    return aGroups==1&&tGroups==1;
}
}
bool ReadIdentity(const StateServices& s,Word unit,Identity& out,const char** failure) {
    if(failure)*failure="identity: header/profile/method mismatch";
    out={};Identity candidate;candidate.address=unit;Word table{},flags{},inside{};
    if(!s.profile||!s.currentIdentity||!s.hitPoints||!s.epoch||!Read(s,unit,0,table)||
        !s.profile->Supports(table)||
        !Method(s,table,0x30,s.profile->retirement)||!Method(s,table,0xC0,s.profile->footprint)||
        !(Method(s,table,0x124,s.profile->attribute)||
          (table==s.profile->building&&s.buildingAttributeReplacement&&
           Method(s,table,0x124,s.buildingAttributeReplacement)))||!Read(s,unit,0x70,candidate.id)||
        !MajestyAttackObservation::Representable(candidate.id)||!Read(s,unit,0x74,flags)||(flags&0x14)||
        !Read(s,unit,0x84,inside)||inside||!Read(s,unit,0x80,candidate.player)||candidate.player>=8||
        !Read(s,unit,0x94,candidate.world)||!candidate.world||
        !Read(s,unit,0x90,candidate.description)||!candidate.description)return false;
    if(failure)*failure="identity: shared current-identity rejected";
    if(!s.currentIdentity(unit,candidate.id,candidate.world,candidate.description))return false;
    if(failure)*failure="identity: hit points/death guard rejected";
    if(s.hitPoints(unit)<=0)return false;
    if(failure)*failure="identity: lifetime epoch rejected";
    candidate.lifetime=s.epoch(unit,candidate.id);if(!candidate.lifetime)return false;
    out=candidate;return true;
}
bool ReadSupportedMover(const StateServices& s,Word actor,Identity& out,const char** failure) {
    Identity identity;Word engine{},map{};Footprint shape;Point pixels;int width{},height{};
    if(failure)*failure="mover: missing descriptor";
    if(!s.actorDescriptor||!ReadIdentity(s,actor,identity,failure))return false;
    if(failure)*failure="mover: selected descriptor mismatch";
    if(identity.description!=s.actorDescriptor)return false;
    if(failure)*failure="mover: engine rejected";
    if(!Engine(s,identity,engine))return false;
    if(failure)*failure="mover: movement rejected";
    if(!NormalMovement(s,identity,engine))return false;
    if(failure)*failure="mover: footprint rejected";
    if(!Shape(s,engine,shape))return false;
    if(failure)*failure="mover: position/map bounds rejected";
    if(!Position(s,actor,pixels)||!Read(s,identity.world,0x90,map)||!Read(s,map,0x50,width)||!Read(s,map,0x54,height)||
        width<1||height<1||width>65535||height>65535||pixels.x>=width*16||pixels.y>=height*16||
        !FitsBounds(shape,{pixels.x/16,pixels.y/16},width,height))return false;
    out=identity;return true;
}
bool ReadPlacement(const StateServices& s,Word actor,Word target,Snapshot& out) {
    out={};Snapshot state;Word actorEngine{},targetEngine{};Point targetPixels{};
    if(!s.revision||!s.actorDescriptor)return false;
    const auto revision=s.revision();
    if(!ReadIdentity(s,actor,state.actor)||!ReadIdentity(s,target,state.target)||
        state.actor.description!=s.actorDescriptor||state.actor.id==state.target.id||!Hostile(s,state.actor,state.target)||
        !Engine(s,state.actor,actorEngine)||!Engine(s,state.target,targetEngine)||
        !NormalMovement(s,state.actor,actorEngine)||!Shape(s,actorEngine,state.mover)||!Shape(s,targetEngine,state.targetShape)||
        !Position(s,actor,state.sourcePixels)||!Position(s,target,targetPixels)||
        !Read(s,state.actor.world,0x90,state.map)||!Read(s,state.map,0x50,state.width)||!Read(s,state.map,0x54,state.height)||
        state.width<1||state.width>65535||state.height<1||state.height>65535||
        state.sourcePixels.x>=state.width*16||state.sourcePixels.y>=state.height*16||
        targetPixels.x>=state.width*16||targetPixels.y>=state.height*16||s.revision()!=revision)return false;
    state.targetTile={targetPixels.x/16,targetPixels.y/16};
    if(!FitsBounds(state.mover,{state.sourcePixels.x/16,state.sourcePixels.y/16},state.width,state.height)||
        !FitsBounds(state.targetShape,state.targetTile,state.width,state.height))return false;
    state.revision=revision;state.verified=true;out=std::move(state);return true;
}
}
