#include "CheckedPlacement.h"
#include <algorithm>
#include <set>
#include <tuple>
#include <limits>

namespace MajestyCheckedPlacement {
namespace {
bool ValidIdentity(const Identity& a) {
    return a.address && a.id && a.id!=0xffffffffu && a.world && a.description && a.lifetime;
}
bool ShapeEqual(const Footprint& a,const Footprint& b) { return a.cells==b.cells; }
bool Supported(const Snapshot& s) {
    return s.verified && ValidIdentity(s.actor) && ValidIdentity(s.target) &&
        s.actor.world==s.target.world && s.actor.id!=s.target.id && s.map &&
        s.width>0 && s.height>0 && s.width<=65535 && s.height<=65535 &&
        s.sourcePixels.x>=0 && s.sourcePixels.y>=0 &&
        s.sourcePixels.x<s.width*16 && s.sourcePixels.y<s.height*16 &&
        s.mover.Valid() && s.targetShape.Valid() &&
        FitsBounds(s.targetShape,s.targetTile,s.width,s.height);
}
}
bool Same(const Identity& a,const Identity& b) {
    return a.address==b.address && a.id==b.id && a.world==b.world &&
        a.player==b.player && a.description==b.description && a.lifetime==b.lifetime;
}
bool Footprint::Valid() const {
    if (cells.empty() || cells.size()>4096) return false;
    std::set<std::pair<int,int>> seen;
    for (auto p:cells) {
        if (p.x < -64 || p.x>64 || p.y < -64 || p.y>64 ||
            !seen.emplace(p.x,p.y).second) return false;
    }
    return true;
}
bool DecodeBitmap(int width,int height,int stride,Point offset,
    const std::vector<std::uint8_t>& bytes,Footprint& out) {
    out.cells.clear();
    if(width<=0||height<=0||width>129||height>129||stride<(width+7)/8||stride>32||
        offset.x < -64||offset.y < -64||offset.x>64||offset.y>64||
        width-1>64-offset.x||height-1>64-offset.y||
        bytes.size()!=static_cast<std::size_t>(stride)*height)return false;
    Footprint decoded;
    for(int y=0;y<height;++y)for(int x=0;x<width;++x)
        if(bytes[static_cast<std::size_t>(y)*stride+x/8]&(1u<<(x&7)))
            decoded.cells.push_back({offset.x+x,offset.y+y});
    if(!decoded.Valid())return false;
    out=std::move(decoded);return true;
}
bool DecodeRectangle(int left,int top,int right,int bottom,Footprint& out) {
    out.cells.clear();
    if(left < -64||top < -64||right>65||bottom>65||left>=right||top>=bottom||
        static_cast<std::int64_t>(right-left)*(bottom-top)>4096)return false;
    for(int y=top;y<bottom;++y)for(int x=left;x<right;++x)out.cells.push_back({x,y});
    return true;
}
bool FitsBounds(const Footprint& shape,Point tile,int width,int height) {
    if (!shape.Valid() || width<=0 || height<=0 || width>65535 || height>65535 ||
        tile.x<0 || tile.y<0 || tile.x>=width || tile.y>=height) return false;
    for (auto cell:shape.cells) {
        const auto x=static_cast<std::int64_t>(tile.x)+cell.x;
        const auto y=static_cast<std::int64_t>(tile.y)+cell.y;
        if (x<0 || y<0 || x>=width || y>=height) return false;
    }
    return true;
}
bool Intersects(const Footprint& a,Point at,const Footprint& b,Point bt) {
    for (auto x:a.cells) for (auto y:b.cells)
        if (static_cast<std::int64_t>(at.x)+x.x==static_cast<std::int64_t>(bt.x)+y.x &&
            static_cast<std::int64_t>(at.y)+x.y==static_cast<std::int64_t>(bt.y)+y.y) return true;
    return false;
}
std::vector<Point> ExteriorSeeds(const Footprint& target,Point targetTile,
    const Footprint& mover,Point source,int width,int height,int range) {
    std::vector<Point> seeds;
    if (!target.Valid() || !mover.Valid() || !FitsBounds(target,targetTile,width,height) ||
        range<=0 || range>MaximumRange || source.x<0 || source.y<0 || source.x>=width*16 || source.y>=height*16)
        return seeds;
    int left=64,right=-64,top=64,bottom=-64,ml=64,mr=-64,mt=64,mb=-64;
    for(auto p:target.cells) { left=std::min(left,p.x);right=std::max(right,p.x);top=std::min(top,p.y);bottom=std::max(bottom,p.y); }
    for(auto p:mover.cells) { ml=std::min(ml,p.x);mr=std::max(mr,p.x);mt=std::min(mt,p.y);mb=std::max(mb,p.y); }
    // Finite exterior perimeter, one tile beyond the target bounds, adjusted
    // for the whole mover. Never sample the center or a substituted endpoint.
    left+=targetTile.x-mr-1;right+=targetTile.x-ml+1;
    top+=targetTile.y-mb-1;bottom+=targetTile.y-mt+1;
    auto add=[&](int x,int y) {
        Point tile{x,y};
        const auto dx=static_cast<std::int64_t>(x)*16-source.x;
        const auto dy=static_cast<std::int64_t>(y)*16-source.y;
        if(dx*dx+dy*dy<=static_cast<std::int64_t>(range)*range &&
            FitsBounds(mover,tile,width,height) && !Intersects(mover,tile,target,targetTile)) seeds.push_back(tile);
    };
    for(int x=left;x<=right;++x) { add(x,top); if(bottom!=top)add(x,bottom); }
    for(int y=top+1;y<bottom;++y) { add(left,y); if(right!=left)add(right,y); }
    std::sort(seeds.begin(),seeds.end(),[&](Point a,Point b) {
        auto distance=[&](Point p) { auto dx=static_cast<std::int64_t>(p.x)*16-source.x,dy=static_cast<std::int64_t>(p.y)*16-source.y;return dx*dx+dy*dy; };
        return std::make_tuple(distance(a),a.y,a.x)<std::make_tuple(distance(b),b.y,b.x);
    });
    return seeds;
}
bool Casts::Accepted(const Identity& a,const Identity& t,Word order,Word action) {
    if (committing_||exhausted_||!ValidIdentity(a)||!ValidIdentity(t)||a.world!=t.world||a.id==t.id||!order||!action||casts_.count(a.id)||casts_.size()>=4096) return false;
    casts_.emplace(a.id,Cast{a,t,order,action,CastPhase::Submitted});return true;
}
bool Casts::Transfer(Word actor,Word oldOrder,Word newOrder,Word action) {
    auto i=casts_.find(actor);
    if(i==casts_.end()||!newOrder||i->second.order!=oldOrder||i->second.action!=action||i->second.phase!=CastPhase::Submitted)return false;
    i->second.order=newOrder;return true;
}
bool Casts::Release(Word actor,Word order,Word action) {
    auto i=casts_.find(actor);
    if(i==casts_.end()||i->second.order!=order||i->second.action!=action||i->second.phase!=CastPhase::Submitted)return false;
    i->second.phase=CastPhase::Released;return true;
}
bool Casts::Matches(const Identity& a,const Identity& t,CastPhase phase) const {
    auto i=casts_.find(a.id);return i!=casts_.end()&&Same(i->second.actor,a)&&Same(i->second.target,t)&&i->second.phase==phase;
}
bool Casts::Consume(const Identity& a,const Identity& t) {
    if(!Matches(a,t,CastPhase::Released))return false;
    casts_.erase(a.id);return true;
}
void Casts::RemovedOrder(Word actor,Word order) {
    auto i=casts_.find(actor);
    if(i!=casts_.end()&&i->second.order==order&&i->second.phase==CastPhase::Submitted)casts_.erase(i);
}
void Casts::InvalidateUnit(Word id) {
    Invalidate();
    for(auto i=casts_.begin();i!=casts_.end();) {
        if(i->second.actor.id==id||i->second.target.id==id)i=casts_.erase(i);else ++i;
    }
}
void Casts::Invalidate() {
    if(invalidation_==std::numeric_limits<std::uint64_t>::max())exhausted_=true;
    else ++invalidation_;
}
void Casts::Reset() { casts_.clear();Invalidate(); }
bool Casts::EnterCommit() { if(committing_||exhausted_)return false;committing_=true;return true; }
void Casts::LeaveCommit() { committing_=false; }
bool SamePlacement(const Snapshot& a,const Snapshot& b) {
    return Supported(a)&&Supported(b)&&Same(a.actor,b.actor)&&Same(a.target,b.target)&&
        a.map==b.map&&a.width==b.width&&a.height==b.height&&a.revision==b.revision&&a.sourcePixels==b.sourcePixels&&
        a.targetTile==b.targetTile&&ShapeEqual(a.mover,b.mover)&&ShapeEqual(a.targetShape,b.targetShape);
}
int Commit(Casts& casts,Native& native,int range,const char** diagnostic) {
    if(diagnostic)*diagnostic="commit reentrancy/exhaustion";
    if(!casts.EnterCommit())return 0;
    struct Scope { Casts& casts;~Scope(){casts.LeaveCommit();} } scope{casts};
    const auto invalidation=casts.Invalidation();
    Snapshot before;
    if(diagnostic)*diagnostic="commit initial capture/authorization";
    if(!native.Capture(before)||!Supported(before)||casts.Invalidation()!=invalidation||
        !casts.Consume(before.actor,before.target))return 0;
    auto stable=[&] {
        Snapshot current;
        return casts.Invalidation()==invalidation&&native.Capture(current)&&
            casts.Invalidation()==invalidation&&SamePlacement(before,current);
    };
    if(diagnostic)*diagnostic="no exterior seeds";
    for(auto tile:ExteriorSeeds(before.targetShape,before.targetTile,before.mover,before.sourcePixels,before.width,before.height,range)) {
        Point pixels{tile.x*16,tile.y*16};
        const bool path=native.CompletePath(before,pixels);
        if(diagnostic)*diagnostic="state changed during path query";
        if(!stable())return 0;
        if(!path){if(diagnostic)*diagnostic="no complete path to exterior seeds";continue;}
        const bool fit=native.FitsTeleport(before,tile);
        if(diagnostic)*diagnostic="state changed during fit query";
        if(!stable())return 0;
        if(!fit){if(diagnostic)*diagnostic="exterior seeds fail footprint fit";continue;}
        if(diagnostic)*diagnostic="stock placement search changed/refused seed";
        if(!native.SelectCheckedSeed(before,pixels))return 0;
        Snapshot checked;
        if(diagnostic)*diagnostic="state changed before cancellation";
        if(!native.Capture(checked)||!SamePlacement(before,checked)||casts.Invalidation()!=invalidation)return 0;
        native.Cancel(checked);
        Snapshot after;
        if(diagnostic)*diagnostic="state changed during cancellation";
        if(!native.Capture(after)||!SamePlacement(checked,after)||casts.Invalidation()!=invalidation)return 0;
        if(diagnostic)*diagnostic="post-cancel path/state rejected";
        if(!native.CompletePath(after,pixels)||!stable())return 0;
        if(diagnostic)*diagnostic="post-cancel fit/state rejected";
        if(!native.FitsTeleport(after,tile)||!stable())return 0;
        Snapshot final;
        if(diagnostic)*diagnostic="final pre-relocation state rejected";
        if(!native.Capture(final)||!SamePlacement(after,final)||casts.Invalidation()!=invalidation)return 0;
        if(diagnostic)*diagnostic="native relocation/write boundary rejected";
        const bool moved=native.Relocate(final,pixels);
        if(moved&&diagnostic)*diagnostic="relocation completed";
        return moved?1:0;
    }
    return 0;
}
}
