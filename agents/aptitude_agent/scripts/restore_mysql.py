"""Restore a dump only when the target schema is confirmed explicitly."""
import argparse
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.engine import make_url


def main():
    parser=argparse.ArgumentParser();parser.add_argument("dump");parser.add_argument("--confirm-schema",required=True);args=parser.parse_args();load_dotenv()
    url=make_url(os.environ["DATABASE_URL"]);dump=Path(args.dump).resolve()
    if url.drivername!="mysql+pymysql":raise SystemExit("DATABASE_URL must use mysql+pymysql")
    if args.confirm_schema!=url.database:raise SystemExit("--confirm-schema must exactly match DATABASE_URL schema")
    if not dump.is_file():raise SystemExit("Dump file not found")
    env=os.environ.copy();env["MYSQL_PWD"]=url.password or ""
    with dump.open("rb") as stream:subprocess.run(["mysql","--host",url.host or "localhost","--port",str(url.port or 3306),"--user",url.username or "root",url.database],stdin=stream,env=env,check=True)
    print(f"Restored {dump} into {url.database}")


if __name__=="__main__":main()
