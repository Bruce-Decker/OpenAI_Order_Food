# Setup

Make sure you have node version 22 installed (minor versions shouldn't matter). If you have a different version of node installed on your computer (check with `node --version`) consider using [nvm](https://github.com/nvm-sh/nvm) to install v22.

Install project dependencies with `npm install`.

## UI Components Setup

This project uses [shadcn-svelte](https://www.shadcn-svelte.com/) components. After installing dependencies, you need to set up the UI components:

1. Run the following command to initialize the UI components:
```bash
npx shadcn-svelte@latest init
```

2. When prompted, select the following options:
   - Style: Default
   - Base color: Slate
   - CSS variables: Yes
   - Tailwind CSS: Yes
   - Components directory: src/lib/components/ui
   - Utils directory: src/lib/utils

3. Add the required components:
```bash
npx shadcn-svelte@latest add button card input
```

## Development

To run the development server:
```bash
npm run dev
```

## Additional

We use:
- [Tailwind CSS](https://tailwindcss.com/) for styling
- [shadcn-svelte](https://www.shadcn-svelte.com/) for components
- [Lucide icons](https://lucide.dev/icons/) for icons

These dependencies are already installed in the project, but you'll need to run the component setup as described above.
