#pragma once
#include "../runtime/AttackObservation.h"
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>
using namespace MajestyAttackObservation;
struct Fixture : Memory {
    std::vector<unsigned char> bytes=std::vector<unsigned char>(0x100000);
    Address next=0x1000, world{},catalog{},actor{},runtime{},head{},last{},treeHead{},treeLast{};
    Profile profile{};
    Fixture() {
        profile.exactExecutable=profile.effectivePackage=profile.lifecycleBound=true;
        profile.allUnitsVtable=0x762E1C; profile.impactFunction=0x4DCF50; profile.projectileId=0x34415041;
        world=Alloc(); runtime=Alloc(); profile.runtimeGlobal=Alloc(); Put(profile.runtimeGlobal,0,runtime);
        Put(runtime,4,world); Put(runtime,0x10,world);
        profile.impactGlobal=Alloc(); Put(profile.impactGlobal,0,profile.impactFunction);
        profile.projectileEngine=Alloc(); profile.movementEngine=Alloc();
        Address text=Alloc(); Put(profile.projectileEngine,0x90,text);
        std::memcpy(bytes.data()+text,"make_attack",12);
        catalog=Alloc(); head=Alloc(); last=head; Put(catalog,0,profile.allUnitsVtable); Put(catalog,0x20,head); Put(head,0,head);
        treeHead=Alloc(); treeLast=treeHead; Put(catalog,0x40,treeHead); Put(treeHead,4,treeHead); bytes[treeHead+0x15]=1;
        actor=Unit(10);
    }
    Address Alloc() { Address result=next; next+=0x200; return result; }
    void Put(Address p,unsigned o,std::uint32_t v) { std::memcpy(bytes.data()+p+o,&v,4); }
    bool Read(Address p,void* output,std::size_t size) const override {
        if (!p || p>bytes.size() || size>bytes.size()-p) return false;
        std::memcpy(output,bytes.data()+p,size); return true;
    }
    Address Unit(unsigned id) {
        Address unit=Alloc(),node=Alloc(); Put(unit,0x70,id); Put(unit,0x94,world); Put(node,0xC,unit);
        Put(node,8,id); Put(last,0,node); Put(node,0,head); last=node;
        auto tree=Alloc(); Put(tree,0xC,id); Put(tree,0,treeHead); Put(tree,8,treeHead);
        Put(treeLast,treeLast==treeHead?4:8,tree); treeLast=tree;
        return unit;
    }
    Address Order(Address unit,unsigned channel,unsigned kind,unsigned terminal) {
        Address stack=Alloc(),sentinel=Alloc(),link=Alloc(),order=Alloc();
        Put(unit,0x98+4*channel,stack); Put(stack,4,unit); Put(stack,0x1C,sentinel);
        Put(sentinel,0,link); Put(link,0,sentinel); Put(link,8,order); Put(order,0x10,kind); Put(order,0x2C,terminal); return order;
    }
    Address Missile(unsigned id) {
        auto unit=Unit(id); auto desc=Alloc(),movement=Alloc();
        Put(unit,0x7C,profile.projectileId); Put(unit,0x90,desc); Put(desc,0x14,profile.projectileEngine);
        Put(unit,0x54,movement); Put(movement,0x14,profile.movementEngine);
        auto order=Order(unit,0,3,0x100A); Put(order,0x5C,10); return order;
    }
    Capture InspectNow() const { return Inspect(*this,profile,world,catalog,actor,10); }
    bool Attach(Lifecycle& life,int mode=0,int status=0) { return life.Attach(*this,profile,status,mode,world,catalog); }
};

