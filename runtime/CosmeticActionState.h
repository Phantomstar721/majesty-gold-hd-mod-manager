#pragma once
#include "CosmeticActionCleanup.h"
#include "CosmeticActionProfiles.h"
#include "AttackObservation.h"
#include <set>

namespace MajestyCheckedPlacement {
// A recovery predicate, NOT admission of a playable effect. The composition
// owner must supply the effective private action/actor descriptors. Matching a
// live part here does not certify its frames, timing, artwork or phase success.
struct CosmeticActionState {
    const MajestyAttackObservation::Memory* memory{};
    const CosmeticImageTypes* types{};
    bool (*identity)(Word,Identity&){};
    Word actorDescriptor{},actionDescriptor{},actionEngine{},actionId{};
    Word requestedSet{0x42},completionSet{8}; // literal stock Standup selectors
    Word approvedImage{};

    template<class T> bool Read(Word p,Word offset,T& out) const {
        return memory&&p&&p<=UINT32_MAX-offset&&sizeof(T)<=UINT32_MAX-p-offset&&
            memory->Read(p+offset,&out,sizeof(out));
    }
    bool Action() const {
        Word id{},subtype{},engine{},table{},scalar[14]{},packet[4]{};
        if(!types||!actionId||!actorDescriptor||!actionDescriptor||!actionEngine||
            !Read(actionDescriptor,4,id)||id!=actionId||!Read(actionDescriptor,8,subtype)||subtype!=1||
            !Read(actionDescriptor,0x14,engine)||engine!=actionEngine||
            !Read(engine,0,table)||table!=types->standardEngine||
            !Read(engine,4,scalar)||!Read(engine,0x3C,packet))return false;
        for(unsigned i=0;i<14;++i)
            if(scalar[i]!=(i==1?requestedSet:i==13?completionSet:0))return false;
        unsigned char first{};
        return !packet[1]&&!packet[2]&&!packet[3]&&
            (!packet[0]||(Read(packet[0],0,first)&&!first));
    }
    bool Collection(Word unit,Word& collection,Word& parts,Word& count) const {
        Word table{},controller{},owner{},descriptor{},engine{},image{},loaded{},resource{},back{};
        return types&&Read(unit,0x28,collection)&&Read(collection,0,table)&&table==types->collection&&
            Read(collection,8,descriptor)&&descriptor&&Read(collection,0x10,owner)&&owner==unit&&
            approvedImage&&Read(actorDescriptor,0x14,engine)&&Read(engine,0x58,image)&&image==approvedImage&&
            Read(collection,4,loaded)&&loaded==approvedImage&&
            Read(descriptor,0,resource)&&Read(resource,0,loaded)&&loaded==approvedImage&&
            Read(resource,0x10,back)&&back==descriptor&&
            Read(collection,0x14,controller)&&!controller&&Read(collection,0x18,count)&&count&&
            count<=UINT32_MAX/0x40&&Read(collection,0x1C,parts)&&parts&&
            count*0x40<=UINT32_MAX-parts;
    }
    bool Part(Word parts,Word count,Word index,CosmeticPose& pose) const {
        if(index>=count)return false;
        Word table{},flags{},attachment{},classification{};
        pose.part=parts+index*0x40;
        const bool valid=Read(pose.part,0,table)&&table==types->part&&
            Read(pose.part,4,pose.imageDescriptor)&&pose.imageDescriptor&&
            Read(pose.part,8,pose.imageSet)&&pose.imageSet==requestedSet&&
            Read(pose.part,0xC,flags)&&!(flags&0xF008)&&
            Read(pose.part,0x10,attachment)&&!attachment&&
            Read(pose.part,0x14,classification)&&!classification&&
            Read(pose.part,0x18,pose.association)&&(!pose.association||(index&&pose.association==parts));
        pose.streamRole=(flags>>8)&0xF;
        return valid&&pose.streamRole<=1;
    }
    bool Channel(Word unit,Word wanted) const {
        Word stack{},owner{},head{},link{};
        if(!Read(unit,0xA0,stack))return false;
        if(!stack)return !wanted;
        if(!Read(stack,4,owner)||owner!=unit||!Read(stack,0x1C,head)||!head||!Read(head,0,link))return false;
        if(!wanted)return link==head;
        std::set<Word> seen;
        while(link!=head) {
            Word order{};
            if(seen.size()>=65536||!seen.insert(link).second||!Read(link,8,order))return false;
            if(order==wanted)return true;
            if(!Read(link,0,link))return false;
        }
        return false;
    }
    bool CanStart(Word unit,bool requireEmptyChannel=true) const {
        Identity actor;Word collection{},parts{},count{},descriptor{},records{},recordCount{};
        if(!identity||!Action()||!identity(unit,actor)||actor.description!=actorDescriptor||
            (requireEmptyChannel&&!Channel(unit,0))||!Collection(unit,collection,parts,count)||
            !Read(collection,8,descriptor)||!Read(descriptor,0xC,recordCount)||
            !recordCount||recordCount>65536||!Read(descriptor,0x10,records)||!records||
            recordCount>(UINT32_MAX-records)/0x2C)return false;
        // The declared actor resource uses one ordinary family, not randomly
        // selected variants. Do not call the native prospective-part helper:
        // that helper can allocate and mutate cached metadata.
        Word record{};
        for(Word i=0;i<recordCount;++i) {
            Word key{};const Word at=records+i*0x2C;
            if(!Read(at,0,key))return false;
            if((key&0xFFFFFF)==requestedSet) {
                if(record||key!=requestedSet)return false;
                record=at;
            }
        }
        Word classification{},directions{},flags{},directionArray{},aux{},cache{},extra{};
        if(!record||!Read(record,4,classification)||classification||
            !Read(record,0x14,aux)||aux||!Read(record,0x18,cache)||
            (cache&&(!Read(cache,0x10,extra)||extra))||
            !Read(record,8,directions)||!directions||directions>32||
            !Read(record,0xC,flags)||
            !Read(record,0x20,directionArray)||!directionArray||
            directions>(UINT32_MAX-directionArray)/0x5C)return false;
        // Stock processor10 creates kind11 for index0 when no earlier part
        // started an animation, even without bit10000. Admit that exact route
        // only for a certified single-stream ordinary set with no extra parts.
        const bool singlePartFallback=!(flags&0x10000);
        if(singlePartFallback&&(flags&0x300)!=0x100)return false;
        for(Word i=0;i<directions;++i) {
            std::int16_t frames{},streams{};Word extraCount{},extraData{};
            const Word direction=directionArray+i*0x5C;
            if(!Read(direction,0x58,frames)||frames<=0||
                (singlePartFallback&&(!Read(direction,0x56,streams)||streams!=1))||
                !Read(direction,0x40,extraCount)||extraCount||!Read(direction,0x44,extraData)||extraData)return false;
        }
        for(Word i=0;i<count;++i) {
            const Word part=parts+i*0x40;Word table{},selected{},partFlags{},attachment{},kind{},association{};
            std::uint16_t direction{};
            if(!Read(part,0,table)||table!=types->part||!Read(part,4,selected)||selected!=descriptor||
                !Read(part,0xC,partFlags)||(partFlags&0xF008)||((partFlags>>8)&0xF)>1||
                !Read(part,0x10,attachment)||attachment||!Read(part,0x14,kind)||kind||
                !Read(part,0x18,association)||(association&&(!i||association!=parts))||
                !Read(part,0x22,direction)||direction>=directions)return false;
        }
        return true;
    }
    bool Capture(Word unit,Word order,CosmeticPose& out) const {
        CosmeticPose pose;Word table{},kind{},action{},index{},phase{},terminal{},flags{},parts{},count{};
        if(!identity||!CanStart(unit,false)||!identity(unit,pose.actor)||pose.actor.description!=actorDescriptor||
            !Channel(unit,order)||!Read(order,0,table)||table!=types->animation||
            !Read(order,0x10,kind)||kind!=11||!Read(order,0x5C,action)||action!=actionId||
            !Read(order,0x50,phase)||phase!=0x1000||!Read(order,0x2C,terminal)||terminal!=0x1001||
            !Read(order,0x34,flags)||flags!=0x150||!Read(order,0x38,index)||
            !Collection(unit,pose.collection,parts,count)||!Part(parts,count,index,pose))return false;
        pose.order=order;pose.action=action;pose.actionDescriptor=actionDescriptor;out=pose;return true;
    }
    bool Current(const CosmeticPose& before) const {
        Identity actor;CosmeticPose now;Word parts{},count{};
        if(!identity||!CanStart(before.actor.address)||before.actionDescriptor!=actionDescriptor||before.action!=actionId||
            !identity(before.actor.address,actor)||!Same(before.actor,actor)||
            !Channel(actor.address,0)||!Collection(actor.address,now.collection,parts,count)||
            now.collection!=before.collection||before.part<parts||(before.part-parts)%0x40||
            !Part(parts,count,(before.part-parts)/0x40,now))return false;
        return now.part==before.part&&now.imageDescriptor==before.imageDescriptor&&now.imageSet==before.imageSet&&
            now.streamRole==before.streamRole&&now.association==before.association;
    }
};
}
