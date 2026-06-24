/* Ultra-light line icons, drawn with currentColor so they inherit accent/text. */

export function Icon({
  path,
  className = '',
  size = 20,
}: {
  path: string;
  className?: string;
  size?: number;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.3"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
      dangerouslySetInnerHTML={{ __html: path }}
    />
  );
}

export const ICONS = {
  // markdown file
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M8.5 13.5v3.5M8.5 13.5l1.7 2 1.7-2v3.5M15 13.5V17M15 17l-1.4-1.6M15 17l1.4-1.6"/>',
  // database / sqlite
  database: '<ellipse cx="12" cy="5.5" rx="7" ry="3"/><path d="M5 5.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/><path d="M5 11.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
  // two machines linked across distance
  machines: '<rect x="2.5" y="6" width="7" height="6" rx="1"/><rect x="14.5" y="12" width="7" height="6" rx="1"/><path d="M6 12v2.5M18 12V9.5"/><path d="M6 14.5h9a1 1 0 0 1 1 1v.5"/>',
  // bolt / automatic
  bolt: '<path d="M13 2 4.5 13.5H11l-1 8.5 8.5-11.5H13z"/>',
  // shield / private
  shield: '<path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="m9.5 12 1.8 1.8 3.5-3.6"/>',
  // browse / map node graph
  map: '<circle cx="6" cy="7" r="2.2"/><circle cx="18" cy="6.5" r="2.2"/><circle cx="13" cy="17.5" r="2.2"/><path d="M8 8.4 11.2 15.6M16.3 8.3 13.9 15.7M8.2 7 15.8 6.7"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  download: '<path d="M12 3v11M8 11l4 4 4-4"/><path d="M5 19h14"/>',
  terminal: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M13 15h4"/>',
  sync: '<path d="M4 7a8 8 0 0 1 14-3l2 2"/><path d="M20 4v4h-4"/><path d="M20 17a8 8 0 0 1-14 3l-2-2"/><path d="M4 20v-4h4"/>',
  github:
    '<path d="M12 2.2A10 10 0 0 0 8.8 21.7c.5.1.7-.2.7-.5v-1.7c-2.8.6-3.4-1.3-3.4-1.3-.5-1.1-1.1-1.4-1.1-1.4-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.5 2.3 1.1 2.9.8.1-.6.3-1.1.6-1.3-2.2-.25-4.5-1.1-4.5-4.9 0-1.1.4-2 1-2.7-.1-.3-.4-1.3.1-2.6 0 0 .8-.3 2.7 1a9.3 9.3 0 0 1 5 0c1.9-1.3 2.7-1 2.7-1 .5 1.3.2 2.3.1 2.6.6.7 1 1.6 1 2.7 0 3.8-2.3 4.6-4.5 4.9.4.3.7.9.7 1.8v2.6c0 .3.2.6.7.5A10 10 0 0 0 12 2.2Z"/>',
};
