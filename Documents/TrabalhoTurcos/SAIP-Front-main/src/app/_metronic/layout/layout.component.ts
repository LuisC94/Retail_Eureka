import {
  Component,
  OnInit,
  ViewChild,
  ElementRef,
  AfterViewInit,
  OnDestroy,
} from '@angular/core';
import { LayoutService } from './core/layout.service';
import { LayoutInitService } from './core/layout-init.service';
import { NavigationCancel, NavigationEnd, Router } from '@angular/router';
import { fromEvent, Subscription } from 'rxjs';
import { WebSocketService } from 'src/app/modules/common/web-socket.service';
import { AuthService } from 'src/app/modules/auth';

@Component({
  selector: 'app-layout',
  templateUrl: './layout.component.html',
  styleUrls: ['./layout.component.scss'],
})
export class LayoutComponent implements OnInit, AfterViewInit, OnDestroy {
  // Public variables
  selfLayout = 'default';
  asideSelfDisplay: true;
  asideMenuStatic: true;
  contentClasses = '';
  contentContainerClasses = '';
  toolbarDisplay = true;
  contentExtended: false;
  asideCSSClasses: string;
  asideHTMLAttributes: any = {};
  headerMobileClasses = '';
  headerMobileAttributes = {};
  footerDisplay: boolean;
  footerCSSClasses: string;
  headerCSSClasses: string;
  headerHTMLAttributes: any = {};
  // offcanvases
  extrasSearchOffcanvasDisplay = false;
  extrasNotificationsOffcanvasDisplay = false;
  extrasQuickActionsOffcanvasDisplay = false;
  extrasCartOffcanvasDisplay = false;
  extrasUserOffcanvasDisplay = false;
  extrasQuickPanelDisplay = false;
  extrasScrollTopDisplay = false;
  asideDisplay: boolean = true;
  @ViewChild('ktAside', { static: true }) ktAside: ElementRef;
  @ViewChild('ktHeaderMobile', { static: true }) ktHeaderMobile: ElementRef;
  @ViewChild('ktHeader', { static: true }) ktHeader: ElementRef;

  isMobile: boolean = true;
  isAdminPanel: boolean = false;

  private unsubscribe: Subscription[] = [];

  constructor(
    private initService: LayoutInitService,
    private layout: LayoutService,
    private router: Router,
    private wsService: WebSocketService,
    private authService: AuthService
  ) {
    this.initService.init();

  }

  setMobility(width: number) {
    if(width >= 992) {
      this.asideDisplay = false;
      this.isMobile = false;

      this.asideCSSClasses = "";
    }
    else{
      this.asideDisplay = true;
      this.isMobile = true;

      this.asideCSSClasses = "aside aside-extended drawer-start drawer";
    }
  }

  ngOnInit(): void {

    let resizeObservable$ = fromEvent(window, 'resize')
    let resizeSubscription$ = resizeObservable$.subscribe( evt => {
      this.setMobility((evt.target as typeof window).innerWidth);
    })

    this.setMobility(window.innerWidth);

    // build view by layout config settings
    this.toolbarDisplay = this.layout.getProp('toolbar.display') as boolean;
    this.contentContainerClasses = this.layout.getStringCSSClasses('contentContainer');
    this.headerCSSClasses = this.layout.getStringCSSClasses('header');
    this.headerHTMLAttributes = this.layout.getHTMLAttributes('headerMenu');
    this.footerCSSClasses = this.layout.getStringCSSClasses('footer')

    // window.addEventListener("resize", this.onresize(this));
  }

  ngAfterViewInit(): void {
    if (this.ktHeader) {
      for (const key in this.headerHTMLAttributes) {
        if (this.headerHTMLAttributes.hasOwnProperty(key)) {
          this.ktHeader.nativeElement.attributes[key] =
            this.headerHTMLAttributes[key];
        }
      }
    }

    this.routingChanges();
  }

  ngOnDestroy(): void {
    this.unsubscribe.forEach((sb) => sb.unsubscribe());
  }

  routingChanges() {
    let currentUser = this.authService.currentUserValue;

    if((!this.wsService.socket || this.wsService.socket.closed) && currentUser) {
      this.wsService.openWebSocket(currentUser.id);
    }
    else{
      this.wsService.closeWebSocket();
    }

    const routerSubscription = this.router.events.subscribe((event) => {

      this.setMobility(window.innerWidth);

      if(currentUser) {
        if(this.router.url.includes("/shopping") || this.router.url.includes("/comments") || this.router.url == "/basketmanagement" || this.router.url.includes("/ordermanagement")) {
          this.isAdminPanel = false;
        }
        else{
          this.isAdminPanel = true;
        }
      }
      else{
        this.isAdminPanel = false;
      }
    });

    this.unsubscribe.push(routerSubscription);
  }
}
