This file contains steps for running migration script for base templates created using create_base_template api.

1 - Exec inside the nb-api
2- Go to tmp directory by running - 'cd /tmp'
3- Copy migration.py at /tmp
4- Run the script in the way mentioned below:
python {file_name}  --host "{host_name}" --database "{database_name}" --user "{user name}" --password "{Database_password}" --port "{port_no}" --options "-c search_path={schema_name}"
Example:
python test.py --host "refract.cqkkwwmb5gtj.us-east-1.rds.amazonaws.com" --database "ai_logistics" --user "postgres" --password "R_PgcoL5yVz2r7_T" --port "5432" --options "-c search_path=ai_logistics"
