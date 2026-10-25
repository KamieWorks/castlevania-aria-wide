"""Keep the user's latest slot-three cartridge SRAM during older private fixture tests."""
from debug_config import debug_root
import pathlib,os,hashlib,json
from harness import Probe,ROOT
tmp=debug_root()
with Probe() as p:
    # Start directly after a fresh slot-three load; never replace a newer save
    # with SRAM from a historical fixture, including our earlier user snapshot.
    meta=p.capture('fixture-isolation-fresh',False)
    assert [meta['area'],meta['room'],meta['playState']]==[0,36,1],meta
    p.call('statesave','fresh',str(tmp/'latest-user-slot3').replace('\\','/'))
    p.call('cartdump',str(tmp/'cart-before.bin').replace('\\','/'))
    try:
        p.call('stateimport','older',str(tmp/'julius-save-room').replace('\\','/'));print(p.call('stateload','older'),flush=True)
        p.call('cartdump',str(tmp/'cart-after.bin').replace('\\','/'))
        before=(tmp/'cart-before.bin').read_bytes();after=(tmp/'cart-after.bin').read_bytes();assert before==after
    finally:p.call('stateload','fresh',False)
    meta=p.capture('user-fixture-isolation-restored',False)
    report={'preserved':True,'bytes':len(before),'sha256':hashlib.sha256(before).hexdigest(),'restoredRoom':[meta['area'],meta['room']]}
(ROOT/'diagnostics-v2/fixture-isolation-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
