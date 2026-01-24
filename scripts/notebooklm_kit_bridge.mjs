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

function extractTextFromRawData(rawData) {
  if (!rawData) return '';
  if (Array.isArray(rawData) && rawData.length > 0) {
    const first = rawData[0];
    if (Array.isArray(first) && first.length > 0 && typeof first[0] === 'string') {
      return first[0];
    }
    if (typeof first === 'string') {
      return first;
    }
  }
  return '';
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

    if (command === 'add-text') {
      const notebookId = getArg('--notebook-id');
      const title = getArg('--title', undefined);
      const contentArg = getArg('--content', undefined);
      const filePath = getArg('--file', undefined);
      if (!notebookId) {
        throw new Error('Missing --notebook-id');
      }

      let content = contentArg;
      if (!content && filePath) {
        content = await readFile(filePath, 'utf-8');
      }
      if (!content) {
        throw new Error('Missing --content or --file');
      }

      const result = await client.sources.addFromText(notebookId, {
        content,
        ...(title ? { title } : {}),
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

    if (command === 'list-sources') {
      const notebookId = getArg('--notebook-id');
      if (!notebookId) {
        throw new Error('Missing --notebook-id');
      }

      const sources = await client.sources.list(notebookId);
      const simplified = (sources || []).map((source) => ({
        sourceId: source.sourceId ?? source.id ?? null,
        title: source.title ?? null,
        status: source.status ?? source.state ?? null,
        type: source.type ?? null,
      }));

      console.log(
        JSON.stringify({
          success: true,
          sources: simplified,
        })
      );
      return;
    }

    if (command === 'chat') {
      const notebookId = getArg('--notebook-id');
      const prompt = getArg('--prompt');
      if (!notebookId || !prompt) {
        throw new Error('Missing --notebook-id or --prompt');
      }

      const response = await client.generation.chat(notebookId, prompt);
      const text = extractTextFromRawData(response.rawData) || response.text || '';
      console.log(
        JSON.stringify({
          success: true,
          text,
          citations: response.citations || [],
          conversationId: response.conversationId || null,
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
