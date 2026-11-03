"""Synthetic algebra fixture, independently constructed; never codec evidence."""
from pathlib import Path
import csv

FIELDS=('record_type','frame','poc','encode_order','slice_type','rc_mode','qCompress',
        'qg_x','qg_y','qg_size','final_qp','base_qp_at_cu','has_residual','skip')


def generate(root: Path):
    for name,base,net in (('zero',30,-4),('plus6',40,2),('minus6',48,-10)):
        rows=[]
        for frame in (0,1):
            identity={'frame':frame,'poc':frame,'encode_order':frame,'slice_type':'I','rc_mode':'CRF','qCompress':.6}
            rows.append({'record_type':'frame',**identity})
            for y in (0,16):
                for x in (0,16):
                    rows.append({'record_type':'cu',**identity,'qg_x':x,'qg_y':y,'qg_size':16,
                        'final_qp':base+net,'base_qp_at_cu':base,'has_residual':1,'skip':0})
        with (root/f'synthetic_{name}.csv').open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator='\n');writer.writeheader();writer.writerows(rows)


if __name__=='__main__':
    generate(Path(__file__).parent)
