import argparse
import os
import sqlite3
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Blueprint §14 restore script")
    parser.add_argument("--backup", required=True, help="Path to backup .db file")
    parser.add_argument("--target", required=True, help="Path to target .db file")
    return parser.parse_args()

def main():
    args = parse_args()
    
    if not os.path.exists(args.backup):
        print(f"Error: Backup file {args.backup} does not exist.")
        sys.exit(1)
        
    try:
        bck_conn = sqlite3.connect(args.backup)
        cursor = bck_conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        if result[0] != "ok":
            print("Error: Backup file fails integrity check.")
            sys.exit(1)
    except Exception as e:
        print(f"Error reading backup database: {e}")
        sys.exit(1)
        
    try:
        tgt_conn = sqlite3.connect(args.target)
        with tgt_conn:
            bck_conn.backup(tgt_conn)
    except Exception as e:
        print(f"Error during restore: {e}")
        sys.exit(1)
    finally:
        bck_conn.close()
        tgt_conn.close()
        
    print(f"Restore verified and completed successfully from {args.backup} to {args.target}.")

if __name__ == "__main__":
    main()
