import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnDestroy,
  OnInit,
  ViewChild,
} from '@angular/core';
import { NavigationCancel, NavigationEnd, Router } from '@angular/router';
import { Subscription } from 'rxjs';
import {
  DrawerComponent,
  MenuComponent,
  ScrollComponent,
  ToggleComponent,
} from 'src/app/_metronic/kt/components';
import { environment } from '../../../../../../../environments/environment';
import { AuthService } from 'src/app/modules/auth';
import { MenuModel } from 'src/app/models/menu.model';

const menuList = [
  {
    "id": 1,
    "name": "Dashboard",
    "nameEn": "Dashboard",
    "url": "/dashboard",
    "icon": undefined,
    "permissionId": 21,
    "isDeleted": false,
    "isSystemData": true,
    "parentId": undefined,
    "parent": undefined,
    "childMenus": [],
    "isForbid": undefined,
  },
  {
    "id": 2,
    "name": "Kullanıcı Yönetimi",
    "nameEn": "User Management",
    "url": undefined,
    "icon": undefined,
    "permissionId": undefined,
    "isDeleted": false,
    "isSystemData": true,
    "parentId": undefined,
    "parent": undefined,
    "isForbid": undefined,
    "childMenus": [
      {
        "id": 3,
        "name": "Yetkiler",
        "nameEn": "Permissions",
        "url": "/usermanagement/permissions",
        "icon": undefined,
        "permissionId": 1,
        "isDeleted": false,
        "isSystemData": true,
        "parentId": 2,
        "parent": undefined,
        "childMenus": [],
        "isForbid": undefined,
      },
      {
        "id": 4,
        "name": "Roller",
        "nameEn": "Roles",
        "url": "/usermanagement/roles",
        "icon": undefined,
        "permissionId": 5,
        "isDeleted": false,
        "isSystemData": true,
        "parentId": 2,
        "parent": undefined,
        "childMenus": [],
        "isForbid": undefined,
      },
      {
        "id": 5,
        "name": "Kullanıcılar",
        "nameEn": "Users",
        "url": "/usermanagement/users",
        "icon": undefined,
        "permissionId": 13,
        "isDeleted": false,
        "isSystemData": true,
        "parentId": 2,
        "parent": undefined,
        "childMenus": [],
        "isForbid": undefined,
      }
    ]
  },
  {
    "id": 6,
    "name": "Organizasyon Yönetimi",
    "nameEn": "Organization Management",
    "url": "/organizationmanagement",
    "icon": undefined,
    "permissionId": 9,
    "isDeleted": false,
    "isSystemData": true,
    "parentId": undefined,
    "parent": undefined,
    "childMenus": [],
    "isForbid": undefined,
  },
  {
    "id": 8,
    "name": "Gelen Sipariş Yönetimi",
    "nameEn": "Incoming Order Management",
    "url": "/incomingordermanagement",
    "icon": undefined,
    "permissionId": 28,
    "isDeleted": false,
    "isSystemData": true,
    "parentId": undefined,
    "parent": undefined,
    "childMenus": [],
    "isForbid": undefined,
  },
  {
    "id": 9,
    "name": "Ürün Yönetimi",
    "nameEn": "Product Management",
    "url": "/productmanagement",
    "icon": undefined,
    "permissionId": 22,
    "isDeleted": false,
    "isSystemData": true,
    "parentId": undefined,
    "parent": undefined,
    "childMenus": [],
    "isForbid": undefined,
  }
]

@Component({
  selector: 'app-menu-tab',
  templateUrl: './menu-tab.component.html',
  styleUrls: ['./menu-tab.component.scss'],
})
export class MenuTabComponent implements OnInit, AfterViewInit, OnDestroy {
  appAngularVersion: string = environment.appVersion;
  appPreviewChangelogUrl: string = environment.appPreviewChangelogUrl;
  @ViewChild('ktAsideScroll', { static: true }) ktAsideScroll: ElementRef;
  private unsubscribe: Subscription[] = [];

  menuList: MenuModel[] = menuList;
  permissionList: number[] | undefined;

  constructor(private router: Router, private authService: AuthService) {}

  ngAfterViewInit(): void {
    
  }

  ngOnInit(): void {
    this.routingChanges();

    this.authService.currentUserSubject.asObservable().subscribe(result => {
      if(result) {
        if (result?.permissions) {
          this.permissionList = (JSON.parse(result?.permissions) as number[]);

          this.menuList.forEach(menu => {
            if (menu.permissionId) {
              if (this.permissionList?.includes(menu.permissionId)) {
                menu.isForbid = false;
              }
              else {
                menu.isForbid = true;
              }
            }
            else {
              menu.childMenus?.forEach(childMenu => {
                if (this.permissionList?.includes(childMenu.permissionId!)) {
                  childMenu.isForbid = false;
                  menu.isForbid = false;
                }
                else {
                  childMenu.isForbid = true;
                }

                if(!childMenu.isForbid) {
                  menu.isForbid = false;
                }
                else {
                  menu.isForbid = true;
                }
              })
            }
          })
        }
      }
    })
  }

  routingChanges() {
    const routerSubscription = this.router.events.subscribe((event) => {
      if (event instanceof NavigationEnd || event instanceof NavigationCancel) {
        this.menuReinitialization();
      }
    });
    this.unsubscribe.push(routerSubscription);
  }

  menuReinitialization() {
    setTimeout(() => {
      MenuComponent.reinitialization();
      DrawerComponent.reinitialization();
      ToggleComponent.reinitialization();
      ScrollComponent.reinitialization();
      if (this.ktAsideScroll && this.ktAsideScroll.nativeElement) {
        this.ktAsideScroll.nativeElement.scrollTop = 0;
      }
    }, 50);
  }

  ngOnDestroy() {
    this.unsubscribe.forEach((sb) => sb.unsubscribe());
  }
}
