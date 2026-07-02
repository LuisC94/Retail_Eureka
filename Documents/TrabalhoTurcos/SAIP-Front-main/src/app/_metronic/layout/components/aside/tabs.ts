type Tab = {
  link:
    | 'menu';
  icon: string;
  tooltip:
    | 'Menu';
};

const tabs: ReadonlyArray<Tab> = [
  {
    link: 'menu',
    icon: './assets/media/icons/duotune/general/gen025.svg',
    tooltip: 'Menu',
  }
];

export { tabs, Tab };
