#!/usr/bin/env node
import { readFile } from 'fs/promises';
import path from 'path';
import { NotebookLMClient } from 'notebooklm-kit';

const args = process.argv.slice(2);

function getArg(name, defaultValue = null) {
  const index = args.indexOf(name);
  if (index === -1 || index + 1 >= args.length) {
    return defaultValue;
  }
  return args[index + 1];
}

function guessMimeType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === '.pdf') return 'application/pdf';
  if (ext === '.md') return 'text/markdown';
  if (ext === '.txt') return 'text/plain';
  if (ext === '.epub') return 'application/epub+zip';
  return undefined;
}

async function main() {
  if (args.length === 0) {
    throw new Error('Missing command');
  }

  const authToken = process.env.NOTEBOOKLM_AUTH_TOKEN;
  const cookies = process.env.NOTEBOOKLM_COOKIES;
  if (!authToken || !cookies) {
    throw new Error('Missing NOTEBOOKLM_AUTH_TOKEN or NOTEBOOKLM_COOKIES');
  }

  const client = new NotebookLMClient({
    authToken,
    cookies,
    autoRefresh: false,
  });

  try {
    await client.connect();

    const command = args[0];
    if (command === 'create-notebook') {
      const title = getArg('--title', '');
      const emoji = getArg('--emoji', undefined);
      const notebook = await client.notebooks.create({ title, emoji });
      console.log(
        JSON.stringify({
          success: true,
          notebookId: notebook.projectId,
          title: notebook.title,
        })
      );
      return;
    }

    if (command === 'add-file') {
      const notebookId = getArg('--notebook-id');
      const filePath = getArg('--file');
      if (!notebookId || !filePath) {
        throw new Error('Missing --notebook-id or --file');
      }

      const content = await readFile(filePath);
      const fileName = path.basename(filePath);
      const mimeType = guessMimeType(filePath);

      const result = await client.sources.addFromFile(notebookId, {
        content,
        fileName,
        ...(mimeType ? { mimeType } : {}),
      });

      if (typeof result === 'string') {
        console.log(
          JSON.stringify({
            success: true,
            sourceId: result,
            sourceIds: [result],
            wasChunked: false,
          })
        );
        return;
      }

      const sourceIds = result.allSourceIds || result.sourceIds || [];
      console.log(
        JSON.stringify({
          success: true,
          sourceIds,
          wasChunked: !!result.wasChunked,
          chunks: result.chunks || [],
        })
      );
      return;
    }

    throw new Error(`Unknown command: ${command}`);
  } finally {
    client.dispose();
  }
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(JSON.stringify({ success: false, error: message }));
  process.exit(1);
});
