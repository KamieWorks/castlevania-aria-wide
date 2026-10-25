"""Compare PE32 DLLs after excluding the PE/export/debug timestamps only."""
import argparse
import hashlib
from pathlib import Path
import struct

def normalized(data):
    data=bytearray(data);pe=struct.unpack_from('<I',data,0x3c)[0]
    assert data[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',data,pe+24)[0]==0x10b
    count=struct.unpack_from('<H',data,pe+6)[0];size=struct.unpack_from('<H',data,pe+20)[0];table=pe+24+size
    def offset(rva):
        for i in range(count):
            virtual_size,address,raw_size,raw=struct.unpack_from('<4I',data,table+i*40+8)
            if address<=rva<address+max(virtual_size,raw_size):return raw+rva-address
        raise ValueError('RVA outside PE sections')
    data[pe+8:pe+12]=b'\0'*4
    export=struct.unpack_from('<I',data,pe+24+96)[0]
    if export:data[offset(export)+4:offset(export)+8]=b'\0'*4
    debug,debug_size=struct.unpack_from('<2I',data,pe+24+96+6*8)
    if debug:
        for i in range(debug_size//28):data[offset(debug)+i*28+4:offset(debug)+i*28+8]=b'\0'*4
    return bytes(data)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('reference',type=Path);parser.add_argument('candidate',type=Path);args=parser.parse_args()
    a,b=map(normalized,[args.reference.read_bytes(),args.candidate.read_bytes()])
    assert a==b,'Differences extend beyond PE timestamps.'
    print('Identical after PE timestamps only; normalized SHA256:',hashlib.sha256(a).hexdigest())
