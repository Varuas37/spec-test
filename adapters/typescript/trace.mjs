// TypeScript syntax adapter for the versioned, non-evidentiary source index.
import { realpathSync, readFileSync } from "node:fs";
import { isAbsolute, relative, resolve, sep, dirname, extname } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import ts from "typescript";

const ID = /^[A-Z][A-Z0-9]*-[0-9]+$/;
const ROLES = new Map([["specTestImplements", "implements"], ["specTestVerifies", "verifies"]]);
const HELPERS = new Set(["specTest", "specProperty"]);
const PILOT_HELPER = fileURLToPath(new URL("./src/spec.ts", import.meta.url));

function getName(name) {
  return name && (ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isNumericLiteral(name))
    ? name.text : undefined;
}

export function scan(file, text, isHelperImport) {
  const tsKind = file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, tsKind);
  if (source.parseDiagnostics.length) {
    throw new Error(`${file}: ${ts.flattenDiagnosticMessageText(source.parseDiagnostics[0].messageText, " ")}`);
  }
  const links = [];
  const seen = new Set();
  const helpers = new Map();
  const lineOf = node => source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
  const link = (specId, role, symbol, node) => {
    const line = lineOf(node);
    if (!ID.test(specId) || !symbol) {
      throw new Error(`${file}:${line}: expected a literal requirement ID and named symbol`);
    }
    const key = JSON.stringify([specId, role, symbol]);
    if (seen.has(key)) throw new Error(`${file}:${line}: duplicate trace link for ${symbol}`);
    seen.add(key);
    links.push({spec_id: specId, role, symbol, line, file, language: "typescript"});
  };
  const tags = (node, symbol) => {
    for (const tag of ts.getJSDocTags(node)) {
      const role = ROLES.get(tag.tagName.text);
      if (role) link(typeof tag.comment === "string" ? tag.comment.trim() : "", role, symbol, tag);
    }
  };
  for (const statement of source.statements) {
    if (ts.isImportDeclaration(statement) && ts.isStringLiteral(statement.moduleSpecifier)
        && isHelperImport(statement.moduleSpecifier.text)) {
      const clause = statement.importClause;
      if (!clause?.isTypeOnly && clause?.namedBindings && ts.isNamedImports(clause.namedBindings)) {
        for (const item of clause.namedBindings.elements) {
          const imported = item.propertyName?.text ?? item.name.text;
          if (!item.isTypeOnly && HELPERS.has(imported)) helpers.set(item.name.text, imported);
        }
      }
    }
  }
  for (const statement of source.statements) {
    if (ts.isClassDeclaration(statement)) {
      const name = getName(statement.name);
      tags(statement, name);
      for (const member of statement.members) {
        const memberName = getName(member.name);
        tags(member, name && memberName ? `${name}${member.modifiers?.some(m => m.kind === ts.SyntaxKind.StaticKeyword) ? "." : "#"}${memberName}` : undefined);
      }
    } else if (ts.isFunctionDeclaration(statement) || ts.isInterfaceDeclaration(statement)
        || ts.isTypeAliasDeclaration(statement)) {
      tags(statement, getName(statement.name));
    } else if (ts.isVariableStatement(statement)) {
      const declarations = statement.declarationList.declarations;
      tags(statement, declarations.length === 1 ? getName(declarations[0].name) : undefined);
    } else {
      tags(statement, undefined);
    }
    if (ts.isExpressionStatement(statement) && ts.isCallExpression(statement.expression)) {
      const call = statement.expression;
      if (ts.isIdentifier(call.expression) && helpers.has(call.expression.text)) {
        const [specId, title] = call.arguments;
        if (!specId || !title || !ts.isStringLiteral(specId) || !ts.isStringLiteral(title)
            || !title.text.trim()) {
          throw new Error(`${file}:${lineOf(call)}: spec helper needs literal ID and title to be indexed`);
        }
        link(specId.text, "verifies", `${helpers.get(call.expression.text)}: ${title.text}`, call);
      }
    }
  }
  return links;
}

function run(args) {
  const root = realpathSync(".");
  const files = [...new Set(args.map(arg => realpathSync(arg)))].sort();
  if (!files.length) throw new Error("usage: node trace.mjs FILE.ts [FILE.tsx ...]");
  const links = files.flatMap(path => {
    const current = relative(root, path);
    if (!current || current === ".." || current.startsWith(`..${sep}`) || isAbsolute(current)
        || ![".ts", ".tsx"].includes(extname(current))) {
      throw new Error("expected a TypeScript file inside the project");
    }
    const file = current.split(sep).join("/");
    return scan(file, readFileSync(path, "utf8"), specifier => {
      if (!specifier.startsWith(".")) return false;
      const candidate = resolve(dirname(path), specifier);
      return candidate === PILOT_HELPER || candidate.replace(/\.js$/, ".ts") === PILOT_HELPER;
    });
  });
  process.stdout.write(JSON.stringify({schema_version: 1, links}, null, 2) + "\n");
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  try { run(process.argv.slice(2)); }
  catch (error) { console.error(error.message); process.exitCode = 2; }
}
