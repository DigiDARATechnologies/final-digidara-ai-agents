# Standalone MySQL database file

`aptitude_ai_mysql.sql` creates the `aptitude_ai_dev` baseline schema. It contains no credentials or sample student records. After importing it, always run the Alembic upgrade command below to install newer production tables and columns.

## Command-line import

From the project root:

```powershell
mysql -u root -p < database\aptitude_ai_mysql.sql
```

PowerShell can have inconsistent behavior with native input redirection. If that command fails, use:

```powershell
cmd /c "mysql -u root -p < database\aptitude_ai_mysql.sql"
```

Enter the MySQL root password when prompted.

## MySQL Workbench import

1. Open MySQL Workbench and connect to the local MySQL server.
2. Select **File > Open SQL Script**.
3. Choose `database/aptitude_ai_mysql.sql`.
4. Run the complete script using the lightning icon.
5. Refresh **Schemas** and verify that `aptitude_ai_dev` exists.

## Application user

Create the application user separately so its password is never stored in the SQL file:

```sql
CREATE USER IF NOT EXISTS 'aptitude_user'@'localhost'
IDENTIFIED BY 'your-strong-local-password';

GRANT ALL PRIVILEGES ON aptitude_ai_dev.*
TO 'aptitude_user'@'localhost';

FLUSH PRIVILEGES;
```

Then put the matching URL in `.env`:

```env
DATABASE_URL=mysql+pymysql://aptitude_user:your-password@localhost:3306/aptitude_ai_dev
```

URL-encode special password characters. For example, `!` becomes `%21` and `@` becomes `%40`.

The SQL file registers baseline revision `0004_native_auth`. Install all later revisions, including the approved question bank, asynchronous diagnostics, and worker heartbeat tables, with:

```powershell
flask --app app db upgrade
```
