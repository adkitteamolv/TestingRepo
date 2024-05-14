import argparse
import psycopg2

# Set up command-line argument parsing
parser = argparse.ArgumentParser()
parser.add_argument("--host", help="the database host", default="refract.cqkkwwmb5gtj.us-east-1.rds.amazonaws.com")
parser.add_argument("--database", help="the database name", default="ai_logistics")
parser.add_argument("--user", help="the database user", default="postgres")
parser.add_argument("--password", help="the database password", default="R_PgcoL5yVz2r7_T")
parser.add_argument("--port", help="the database password", default="R_PgcoL5yVz2r7_T")
parser.add_argument("--options", help="database connection options")
args = parser.parse_args()
print(args.options)

# Connect to the database
if args.options:
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
        options=args.options
    )
else:
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
    )

# Rest of the script...

# Create a cursor object to execute SQL queries
cur = conn.cursor()

# Create the uuid-ossp extension if it does not exist
cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")

# Define the SQL query
query = """
SELECT id,
       split_part(name, '-', 1) AS name_first_part,
       split_part(name, '-', 2) AS name_second_part
FROM nb_docker_image 
WHERE id IN (
  SELECT DISTINCT(nb_docker_image_tag.docker_image_id)
  FROM nb_docker_image_tag
  WHERE docker_image_id IN (
    SELECT id 
    FROM nb_docker_image
    WHERE base_image_id IS NULL 
      AND TYPE='PRE_BUILD' 
      AND kernel_type IN ('rstudio', 'python', 'spark_distributed', 'spark')
      AND NOT EXISTS (
        SELECT 1 
        FROM nb_docker_image_tag
        WHERE nb_docker_image_tag.docker_image_id = nb_docker_image.id
          AND tag LIKE 'version%'
      )
    )
);

"""

# Execute the query
cur.execute(query)

# Fetch all the results
results = cur.fetchall()
print(results)
# Open a file to write the insert queries
with open('insert_queries.sql', 'w') as f:
    # Loop through the results and write insert queries to the file
    for row in results:
        # Check if row[2] is None or empty
        version = row[2] if row[2] else 'default'
        import uuid
        id = uuid.uuid4()
        f.write(f"INSERT INTO nb_docker_image_tag(id, created_by, tag, updated_by, docker_image_id) VALUES ('{id}', 'system', 'version={version}', 'system', '{row[0]}');\n")

# Execute the insert queries
cur.execute(open('insert_queries.sql', 'r').read())

# Commit the changes to the database
conn.commit()

# Close the cursor and database connection
cur.close()
conn.close()

'''
Way to run the script
python {file_name} (example-test.py) --host "refract.cqkkwwmb5gtj.us-east-1.rds.amazonaws.com" --database "ai_logistics" --user "postgres" --password "R_PgcoL5yVz2r7_T" --port "5432" --options "-c search_path=ai_logistics"
'''