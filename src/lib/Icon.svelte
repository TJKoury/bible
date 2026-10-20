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
    moon: 'M20.8 13A9 9 0 0 1 11 3.2 9 9 0 1 0 20.8 13Z',
    sun: 'M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5',
    map: 'm3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6m6-3v15m6-12v15',
    pin: 'M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Zm-5 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
    compass: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0m-5-5-6 3-3 6 6-3 3-6Z',
    spark: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z',
    cpu: 'M6 6h12v12H6V6m3-4v4m6-4v4m-6 12v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4M9 9h6v6H9V9',
    copy: 'M9 8h11v13H9V8M15 8V3H4v13h5',
  };
</script>

<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d={paths[name] || paths.book} /></svg>
