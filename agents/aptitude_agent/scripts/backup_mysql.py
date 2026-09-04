"""Create a timestamped, transactional MySQL dump from DATABASE_URL."""
import argparse
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.engine import make_url


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output-dir",default="backups");args=parser.parse_args();load_dotenv()
    url=make_url(os.environ["DATABASE_URL"])
    if url.drivername!="mysql+pymysql":raise SystemExit("DATABASE_URL must use mysql+pymysql")
    output_dir=Path(args.output_dir).resolve();output_dir.mkdir(parents=True,exist_ok=True)
    filename=f"{url.database}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.sql";target=output_dir/filename
    env=os.environ.copy();env["MYSQL_PWD"]=url.password or ""
    command=["mysqldump","--single-transaction","--routines","--triggers","--set-gtid-purged=OFF","--host",url.host or "localhost","--port",str(url.port or 3306),"--user",url.username or "root","--result-file",str(target),url.database]
    subprocess.run(command,env=env,check=True)
    if not target.exists() or target.stat().st_size==0:raise SystemExit("Backup file is empty")
    print(f"Backup created: {target} ({target.stat().st_size} bytes)")


if __name__=="__main__":main()
