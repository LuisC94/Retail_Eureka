import { Component, Input, OnInit } from '@angular/core';
import { forkJoin, Observable } from 'rxjs';
import { ThemeModeService, ThemeModeType } from './theme-mode.service';
import { TranslateService } from '@ngx-translate/core';

@Component({
  selector: 'app-theme-mode-switcher',
  templateUrl: './theme-mode-switcher.component.html',
})
export class ThemeModeSwitcherComponent implements OnInit {
  @Input() toggleBtnClass: string = '';
  @Input() toggleBtnIconClass: string = 'svg-icon-2';
  @Input() menuPlacement: string = 'bottom-end';
  @Input() menuTrigger: string = "{default: 'click', lg: 'hover'}";
  mode$: Observable<ThemeModeType>;
  menuMode$: Observable<ThemeModeType>;

  light: string = "";
  dark: string = "";
  system: string = "";

  constructor(private modeService: ThemeModeService, private translate: TranslateService) {}

  ngOnInit(): void {
    this.mode$ = this.modeService.mode.asObservable();
    this.menuMode$ = this.modeService.menuMode.asObservable();
    this.loadTranslations();
  }

  switchMode(_mode: ThemeModeType): void {
    this.modeService.switchMode(_mode);
  }

  loadTranslations() {
    forkJoin([
      this.translate.get('LIGHT'),
      this.translate.get('DARK'),
      this.translate.get('SYSTEM')
    ]).subscribe(([lightTranslation, darkTranslation, systemTranslation]) => {
      this.light = lightTranslation;
      this.dark = darkTranslation;
      this.system = systemTranslation;
    });

    this.translate.onLangChange.subscribe(() => {
      forkJoin([
        this.translate.get('LIGHT'),
        this.translate.get('DARK'),
        this.translate.get('SYSTEM')
      ]).subscribe(([lightTranslation, darkTranslation, systemTranslation]) => {
        this.light = lightTranslation;
        this.dark = darkTranslation;
        this.system = systemTranslation;
      });
    });
  }
}
