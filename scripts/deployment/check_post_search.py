import psycopg2, os
conn = psycopg2.connect(
    host='ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech',
    dbname='neondb', user='neondb_owner',
    password=os.getenv('DB_PASSWORD','npg_4mNWuybHc6sD'), sslmode='require'
)
cur = conn.cursor()
cur.execute('SELECT post_id, title, all_ai_tags, all_ai_scenes, updated_at FROM read_model_post_search ORDER BY post_id DESC LIMIT 15')
rows = cur.fetchall()
if not rows:
    print('read_model_post_search is EMPTY')
else:
    print(f'{len(rows)} entries in read_model_post_search:')
    for r in rows:
        print(f'  post_id={r[0]}  title={r[1]}')
        print(f'    tags={r[2]}')
        print(f'    scenes={r[3]}')
        print(f'    updated={r[4]}')
conn.close()
