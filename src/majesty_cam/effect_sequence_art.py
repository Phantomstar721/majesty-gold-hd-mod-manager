"""Bake the owned sequence into a stock-shaped, spell-unit IMAG resource.

Input is Export-EffectSequence.cpp's output. Existing stock TILE pixels/palettes
are referenced unchanged. No actor stream, action flags or hide API is touched.
Runtime timing and spell-unit anchoring require ordinary visual acceptance.
"""
import struct
from .art import parse_stock_imag_tile_references


def _point(value):
    if not isinstance(value, list) or len(value)!=2 or any(type(n) is not int or not -32768<=n<=32767 for n in value):
        raise ValueError('effect sequence offset must contain signed16 coordinates')
    return value


def bake_arrival(projectile_imag, impact_imag, samples, *, tile_count):
    """Return IMAG bytes only; caller owns private IDs and reviewed deployment.

    Single Special set/one direction/one group, cloned from the inspected WPg3
    layout. Reusing stock 100ms timing does not prove exact wall-clock cadence.
    Impact/fade use stock decay frames; no unproved alpha flag is invented.
    """
    if not isinstance(samples, dict) or set(samples)!={'schema','period','duration','frames'}:
        raise ValueError('unknown effect sequence sample schema')
    if (any(type(samples[key]) is not int for key in ('schema','period','duration'))
            or samples['schema']!=1 or samples['period']!=100 or samples['duration']!=900):
        raise ValueError('unsupported effect sequence timing')
    frames=samples['frames']
    if not isinstance(frames,list) or len(frames)!=9:
        raise ValueError('expected nine bounded sampled occurrences')
    missile=parse_stock_imag_tile_references(projectile_imag,tile_count=tile_count)
    impact=parse_stock_imag_tile_references(impact_imag,tile_count=tile_count)
    # Exact version4 compact envelope of the inspected stock missile. Do not
    # relocate unknown optional timing/rectangle/group structures by guessing.
    if (len(projectile_imag)!=172 or struct.unpack_from('<III',projectile_imag,20)!=(1,64,32)
            or struct.unpack_from('<I',projectile_imag,32)[0]!=1
            or struct.unpack_from('<I',projectile_imag,96)[0]!=68
            or struct.unpack_from('<I',projectile_imag,104)[0]!=(6<<16)|1
            or any(projectile_imag[108:118])
            or struct.unpack_from('<H',projectile_imag,118)[0]!=1
            or len(missile.references)!=6):
        raise ValueError('stock missile envelope changed or unsupported')
    heads=[r.encoded_value for r in missile.references]
    impacts=[r.encoded_value for r in impact.references if r.set_id==96 and r.direction==0]
    if not impacts or any(r & 0x58000000 for r in heads+impacts):
        raise ValueError('expected visible stock meteor references')
    lanes=[[] for _ in range(9)]
    for index,frame in enumerate(frames):
        if not isinstance(frame,dict) or set(frame)!={'phase','xy','opacity','trail'}:
            raise ValueError('unknown effect frame fields')
        expected_phase=1 if index<5 else 2 if index<7 else 3
        if type(frame['phase']) is not int or frame['phase']!=expected_phase:
            raise ValueError('effect phases must preserve descent/impact/fade order')
        point=_point(frame['xy']);trail=frame['trail']
        if not isinstance(trail,list) or len(trail)>8 or (index>=5 and trail):
            raise ValueError('invalid bounded effect trail')
        if type(frame['opacity']) is not int or not 0<frame['opacity']<=1000:
            raise ValueError('invalid sampled opacity')
        if index>=5 and point!=[0,0]:raise ValueError('impact must be at its fixed ground anchor')
        ref=heads[index%len(heads)] if index<5 else impacts[min((index-5)*len(impacts)//4,len(impacts)-1)]
        lanes[0].append(struct.pack('<hhI',*point,ref))
        for lane in range(8):
            if lane<len(trail):
                xy=_point(trail[lane]);word=heads[(index+lane)%len(heads)]
            else:
                xy=[0,0];word=heads[0]|0x40000000 # proven skipped EFFECT stream
            lanes[lane+1].append(struct.pack('<hhI',*xy,word))
    header=bytearray(projectile_imag[:124])
    struct.pack_into('<I',header,32+28,100)
    struct.pack_into('<I',header,104,(9<<16)|9)
    return bytes(header)+b''.join(pair for lane in lanes for pair in lane)
