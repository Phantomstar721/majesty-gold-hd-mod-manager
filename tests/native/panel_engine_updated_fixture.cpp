// The pinned upstream source precedes this fixture. Native providers are local
// doubles; no process, game address or installed resource is accessed.
static int __fastcall updatedAttribute(void* target,void*,u32 code,int fallback) {
    REQUIRE(target==&token && code==190206017u && fallback==0); return 1;
}
static void* __fastcall updatedGameString(void*,void*,int id) {
    REQUIRE(id==7); returnedString="Seven"; return &returnedString;
}
static u32 updatedBackground,updatedKey;
static void __fastcall updatedSetArt(void*,void*,u32 set) { updatedBackground=set; }
static void __fastcall updatedArtKey(void*,void*,int key) { updatedKey=key; }
static void runUpdatedFixture() {
    Line L;
    REQUIRE(parse_line("WE|1|BKG|1001|ART1",&L) && L.kind==KIND_BKG && L.control==1001 && L.number==window_id("ART1"));
    REQUIRE(parse_line("WE|1|TEXTPICK|200|PickText|first~second",&L) && L.kind==KIND_TEXTPICK && is(L.fn,"PickText"));
    REQUIRE(parse_line("WE|1|HINTPICK|200|@190206017|off~on",&L) && L.kind==KIND_HINTPICK);
    REQUIRE(parse_line("WE|1|RTEXT|500|#|Row %d",&L) && L.kind==KIND_RTEXT && is(L.fn,"#"));
    REQUIRE(parse_line("WE|1|RTEXTPICK|500|PickRow|off~on",&L) && L.kind==KIND_RTEXTPICK);
    REQUIRE(parse_line("WE|1|RICON|500|RowIcon|ART1",&L) && L.kind==KIND_RICON && L.number==window_id("ART1"));
    REQUIRE(parse_line("WE|1|RHINT|500|#|Row %t",&L) && L.kind==KIND_RHINT);
    REQUIRE(parse_line("WE|1|RHINTPICK|500|#|off~on",&L) && L.kind==KIND_RHINTPICK);
    REQUIRE(parse_line("WE|1|TITLE|8005",&L) && L.kind==KIND_TITLE && L.control==8005);
    REQUIRE(parse_line("WE|1|SPELL|8730|SP01|ART1~1002~Spell~Hint~0",&L) && L.kind==KIND_SPELL && L.number==window_id("SP01"));
    REQUIRE(parse_line("WE|1|EFFECT|8731|EF01|~~Effect~~1",&L) && L.kind==KIND_EFFECT);
    REQUIRE(parse_line("WE|1|TABLE|500|*spells+all+anylevel|501~2~26~28",&L) && L.kind==KIND_TABLE);
    fixture_GET_ATTR=updatedAttribute;
    int ok=0;
    REQUIRE(call_gpl2(&token,"@190206017",0,0,&ok)==1 && ok);
    REQUIRE(row_source(&token,"#",2,99)==99);
    REQUIRE(row_source(&token,"@190206017",2,99)==1);
    char out[64];
    pick_nth("first~second",1,out,sizeof out); REQUIRE(is(out,"second"));
    pick_nth("first~second",2,out,sizeof out); REQUIRE(!out[0]);
    fixture_GAME_STRING=updatedGameString;
    format_text(out,sizeof out,"Name %t",7); REQUIRE(is(out,"Name Seven"));
    static void* updatedDialogTable[57];
    updatedDialogTable[DLG_SETART/4]=(void*)updatedSetArt;
    setPointer(dialogBytes,0,updatedDialogTable);
    fixture_ART_KEY=updatedArtKey;
    rowText[0]="WE|1|BKG|1001|ART1";*(int*)(tableBytes+0x0c)=1;
    keep_background(controllerBytes,0);
    REQUIRE(updatedBackground==window_id("ART1") && updatedKey==1001);
}
