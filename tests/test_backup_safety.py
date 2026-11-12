import gzip
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
from flask import Flask
import tempfile
import time

HERE=Path(__file__).resolve().parent
def module():
    spec=importlib.util.spec_from_file_location('backup_fix_candidate',HERE.parent/'backend/backup_routes.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result
def worker(folder,barrier):
    m=module();m.BACKUP_DIR=folder
    def event(name):
        with open(Path(folder)/'events.log','a',encoding='utf-8') as stream:stream.write(name+'\n')
        time.sleep(.15)
    m._backup_mysql=lambda:event('mysql')
    m._backup_milvus=lambda:event('milvus')
    m._cleanup_old_backups=lambda count:None
    barrier.wait(timeout=30)
    m._scheduled_backup_tick(24,10,now=1000000)

def main():
    passed=[];m=module()
    with tempfile.TemporaryDirectory(prefix='isolated-backup-test-',dir=HERE) as directory:
        folder=Path(directory).resolve();assert folder.is_relative_to(HERE.resolve())
        m.BACKUP_DIR=str(folder)
        names=[m._timestamp() for _ in range(1000)]
        assert len(set(names))==1000;passed.append('1000-unique-backup-names')
        target=folder/'mysql_backup_sample.sql.gz'
        with m._atomic_gzip(str(target),'wb') as stream:
            stream.write(b'synthetic-data');assert not target.exists()
        assert gzip.open(target,'rb').read()==b'synthetic-data';passed.append('publish-only-after-close-and-crc')
        sidecar=folder/('.'+target.name+'.verified.json')
        assert json.loads(sidecar.read_text())['gzip_crc_verified'] and not sidecar.name.startswith(('mysql_backup_','milvus_backup_'));passed.append('completed-backup-integrity-sidecar')
        original=target.read_bytes()
        try:
            with m._atomic_gzip(str(target),'wb'):pass
        except FileExistsError:pass
        else:raise AssertionError('Overwrote old backup')
        assert target.read_bytes()==original;passed.append('existing-backup-protected')
        failed=folder/'milvus_backup_failure.jsonl.gz'
        try:
            with m._atomic_gzip(str(failed),'wt') as stream:
                stream.write('{"synthetic":true}\n');raise RuntimeError('expected interruption')
        except RuntimeError:pass
        assert not failed.exists() and not list(folder.glob('*.partial'));passed.append('failed-writer-not-published')
        context=multiprocessing.get_context('spawn');barrier=context.Barrier(4)
        workers=[context.Process(target=worker,args=(str(folder),barrier)) for _ in range(4)]
        for process in workers:process.start()
        for process in workers:
            process.join(40);assert process.exitcode==0,process.exitcode
        assert (folder/'events.log').read_text().splitlines()==['mysql','milvus'];passed.append('four-processes-single-scheduled-backup')
        events=[]
        m._backup_mysql=lambda:events.append('mysql');m._backup_milvus=lambda:events.append('milvus');m._cleanup_old_backups=lambda count:None
        m._scheduled_backup_tick(24,10,now=1000060);assert not events
        m._scheduled_backup_tick(24,10,now=1000000+86401);assert events==['mysql','milvus'];passed.append('interval-preserved-and-next-backup-allowed')
        state=folder/'.scheduled_backup_state.json';state.unlink()
        m._backup_mysql=lambda:(_ for _ in ()).throw(RuntimeError('expected failure'))
        events.clear();m._scheduled_backup_tick(24,10,now=2000000);assert events==['milvus']
        m._scheduled_backup_tick(24,10,now=2000060);assert events==['milvus']
        m._scheduled_backup_tick(24,10,now=2000301);assert events==['milvus','milvus'];passed.append('failure-cooldown-and-retry')
        partial=folder/'mysql_backup_active.sql.gz.writer.partial';partial.write_bytes(b'in-progress')
        m=module();m.BACKUP_DIR=str(folder)
        for i in range(3):
            with gzip.open(folder/f'mysql_backup_{i}.sql.gz','wb') as stream:stream.write(b'test')
        for i in range(3):
            with m._atomic_gzip(str(folder/f'mysql_backup_verified_{i}.sql.gz'),'wb') as stream:stream.write(b'test')
        m._cleanup_old_backups(1)
        assert partial.exists() and all((folder/f'mysql_backup_{i}.sql.gz').exists() for i in range(3))
        assert len(list(folder.glob('mysql_backup_verified_*.sql.gz')))<=1
        passed.append('cleanup-preserves-partials-and-unverified-legacy-files')
        app=Flask('isolated-backup-list')
        m.register_backup_routes(app,engine=None,protected=lambda f:f,admin_required=lambda f:f)
        response=app.test_client().get('/api/backup/list')
        assert response.status_code==200
        payload=response.get_json()
        listed=payload.get('files',[])
        assert listed and all(item['filename'].endswith(('.sql.gz','.jsonl.gz')) for item in listed)
        passed.append('backup-list-hides-partials-and-integrity-sidecars')
    result={'passed':passed,'passed_cases':len(passed),'database_calls':0,'production_source_modified':False,'platform':os.name,'locking':'msvcrt' if os.name=='nt' else 'fcntl','test_storage':'temporary isolated directory only'}
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
