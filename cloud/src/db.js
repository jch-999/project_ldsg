export async function all(db, sql, params = []) {
  const statement = prepare(db, sql, params);
  const result = await statement.all();
  return result.results || [];
}

export async function first(db, sql, params = []) {
  const statement = prepare(db, sql, params);
  const result = await statement.first();
  return result || null;
}

export async function run(db, sql, params = []) {
  const statement = prepare(db, sql, params);
  return statement.run();
}

export async function batch(db, statements) {
  return db.batch(statements);
}

function prepare(db, sql, params) {
  const statement = db.prepare(sql);
  return params.length ? statement.bind(...params) : statement;
}

export function newId() {
  return crypto.randomUUID().replace(/-/g, "");
}

export function nowText() {
  return new Date().toISOString().slice(0, 19);
}
