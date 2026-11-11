static void* managedMethods[17];
static int managerSetups, managerCommands, managerEvents, managerDeletes, captures, aliases;
static int labels;
static void __fastcall fixedLabel(void*,void*,u32 control,const char* text) {
    REQUIRE(control==8005 && text && *text); ++labels;
}
static void __fastcall managedSetup(void* self,void* edx) {
    REQUIRE(MMWE_OwnsController(self)); ++managerSetups; initialize(self,edx);
}
static int __fastcall managedCommand(void* self,void* edx,u32 id) {
    REQUIRE(MMWE_OwnsController(self)); ++managerCommands;
    return command(self,edx,id);
}
static void __fastcall managedEvent(void* self,void* edx,u32 a,u32 b,u32 c,u32 d) {
    REQUIRE(MMWE_OwnsController(self)); ++managerEvents; event(self,edx,a,b,c,d);
}
static void* __fastcall managedDelete(void* self,void* edx,int flags) {
    REQUIRE(MMWE_OwnsController(self)); ++managerDeletes; return destroy(self,edx,flags);
}
static void __cdecl captureManaged(void* self,void* view,void* target) {
    REQUIRE(self==controllerBytes && view==viewBytes && target==&token);
    REQUIRE(*(void***)self==stockVtable+1);
    ++captures; *(void***)self=managedMethods;
}
static int __cdecl describeManaged(void** table,unsigned* count,void** locator) {
    if (table!=managedMethods) return 0;
    *count=17; *locator=stockVtable[0]; return 1;
}
static int __cdecl wrappedManaged(void* self,void** managed,void** presented) {
    REQUIRE(self==controllerBytes && managed==managedMethods && presented==*(void***)self);
    REQUIRE(presented[-1]==stockVtable[0] && presented!=managed && MMWE_OwnsController(self));
    ++aliases; return 1;
}
static void runHandoffFixture() {
    for (int i=0;i<17;++i) managedMethods[i]=stockVtable[i+1];
    managedMethods[SLOT_INIT]=(void*)managedSetup;
    managedMethods[SLOT_ONCOMMAND]=(void*)managedCommand;
    managedMethods[SLOT_ONEVENT]=(void*)managedEvent;
    managedMethods[0]=(void*)managedDelete;
    PanelEngineHandoff::Callbacks callbacks={sizeof(callbacks),1,captureManaged,describeManaged,wrappedManaged};
    REQUIRE(!MMWE_BindHandoff(0));
    --callbacks.size; REQUIRE(!MMWE_BindHandoff(&callbacks)); ++callbacks.size;
    REQUIRE(MMWE_BindHandoff(&callbacks) && MMWE_BindHandoff(&callbacks));
    // A declared controller needs no BASE/CLASS and no replacement action.
    rowText[0]="WE|1|HIDE|10"; rowText[1]="WE|1|DOES|40|30208";
    *(int*)(tableBytes+12)=2;
    const int startClasses=g_nclasses;
    for (int i=0;i<2;++i) {
        construct(controllerBytes,0,viewBytes,&token);
        REQUIRE(WE_Factory(0,0,0x32504146,viewBytes,&token,23)==controllerBytes);
        void** table=*(void***)controllerBytes;
        ((Init_t)table[SLOT_INIT])(controllerBytes,0);
        REQUIRE(((OnCommand_t)table[SLOT_ONCOMMAND])(controllerBytes,0,30209)==9);
        REQUIRE(lastCommand==30209);
        REQUIRE(((OnCommand_t)table[SLOT_ONCOMMAND])(controllerBytes,0,40)==9 && lastCommand==30208);
        ((Notify_t)table[SLOT_ONEVENT])(controllerBytes,0,1,0,2,3);
        REQUIRE(((Dtor_t)table[0])(controllerBytes,0,0x37)==&token && deleteFlags==0x37);
    }
    REQUIRE(captures==2 && aliases==2 && managerSetups==2 && managerCommands==4 && managerEvents==2 && managerDeletes==2);
    REQUIRE(g_nclasses==startClasses+1); // table per class, not per instance
#ifdef MMM_CANDIDATE_LABEL_COUNT
    viewVtable[VIEW_SETTEXT_C/4]=(void*)fixedLabel;
    for (int i=0;i<MMM_CANDIDATE_LABEL_COUNT;++i) {
        rowText[0]=candidateLabels[i]; *(int*)(tableBytes+12)=1;
        construct(controllerBytes,0,viewBytes,&token);
        REQUIRE(WE_Factory(0,0,0x32504146,viewBytes,&token,23)==controllerBytes);
        void** table=*(void***)controllerBytes;
        ((Init_t)table[SLOT_INIT])(controllerBytes,0);
        REQUIRE(((OnCommand_t)table[SLOT_ONCOMMAND])(controllerBytes,0,30209)==9 && lastCommand==30209);
        ((Notify_t)table[SLOT_ONEVENT])(controllerBytes,0,1,0,2,3);
        REQUIRE(((Dtor_t)table[0])(controllerBytes,0,0x37)==&token);
    }
    REQUIRE(labels>=MMM_CANDIDATE_LABEL_COUNT && captures==2+MMM_CANDIDATE_LABEL_COUNT);
    REQUIRE(managerCommands==4+MMM_CANDIDATE_LABEL_COUNT && managerDeletes==2+MMM_CANDIDATE_LABEL_COUNT);
    REQUIRE(g_nclasses==startClasses+1);
#endif
}
