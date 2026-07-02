import {
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  OnInit,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import { NavigationCancel, NavigationEnd, Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { LayoutService } from '../../core/layout.service';
import { MenuComponent } from '../../../kt/components';
import { AuthService } from 'src/app/modules/auth';

@Component({
  selector: 'app-header',
  templateUrl: './header.component.html',
})
export class HeaderComponent implements OnInit, OnDestroy {
  headerContainerCssClasses: string = '';
  @ViewChild('ktPageTitle', { static: true }) ktPageTitle: ElementRef;
  @Input() isAdminPanel: boolean;
  isUserLoggedIn: boolean;
  @Input() isMobile: boolean;

  private unsubscribe: Subscription[] = [];

  constructor(private layout: LayoutService, private router: Router, private auth: AuthService) {
    this.routingChanges();
  }

  ngOnInit(): void {
    this.headerContainerCssClasses =
      this.layout.getStringCSSClasses('headerContainer');

      this.auth.currentUserSubject.subscribe( result => {
        if(result) {
          this.isUserLoggedIn = true;
        }
        else{
          this.isUserLoggedIn = false;
        }
      })
  }



  routingChanges() {
    const routerSubscription = this.router.events.subscribe((event) => {
      if (event instanceof NavigationEnd || event instanceof NavigationCancel) {
        MenuComponent.reinitialization();
      }
    });
    this.unsubscribe.push(routerSubscription);
  }

  ngOnDestroy() {}

}
