<script>
  let { name, size = 19 } = $props();
  const paths = {
    search: 'M21 21l-5-5M18 10.5a7.5 7.5 0 1 1-15 0 7.5 7.5 0 0 1 15 0',
    book: 'M12 5C8 2 3 3 2 4v15c3-2 7-1 10 1m0-15c4-3 9-2 10-1v15c-3-2-7-1-10 1V5',
    library: 'M4 3v18M8 3v18M12 3v18M16 4l5 16',
    bookmark: 'M6 3h12v18l-6-4-6 4V3',
    'arrow-up-right': 'M6 18 18 6M6 6h12v12',
    'arrow-right': 'M4 12h16m-6-6 6 6-6 6',
    'chevron-left': 'm14 6-6 6 6 6',
    'chevron-right': 'm10 6 6 6-6 6',
    expand: 'M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5',
    pointer: 'm5 3 14 9-7 1-3 7L5 3',
    globe: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M3 12h18M12 3c-5 5-5 13 0 18 5-5 5-13 0-18',
    download: 'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
    check: 'm5 12 4 4L19 6',
    x: 'm6 6 12 12M6 18 18 6',
    menu: 'M4 6h16M4 12h16M4 18h16',
    trash: 'M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7',
  };
</script>

<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d={paths[name] || paths.book} /></svg>
