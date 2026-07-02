import { Component, Input, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { TranslateService } from '@ngx-translate/core';
import { NotificationService } from 'src/app/_metronic/partials/layout/extras/dropdown-inner/notifications-inner/notification.service';
import { NotificationModel } from 'src/app/models/notification.model';
import { AuthService } from 'src/app/modules/auth';
import { UserModel } from 'src/app/modules/user-management/models/user.model';
import { UserManagementService } from 'src/app/modules/user-management/user-management.service';

@Component({
  selector: 'app-topbar',
  templateUrl: './topbar.component.html',
})
export class TopbarComponent implements OnInit {

  @Input() isAdminPanel: boolean = true;
  hasShoppingPermission: boolean = true;
  isAdmin: boolean = false;
  isCurrentUserExist: boolean = true;
  user: UserModel;

  unreadedNotificationCount: number = 0;
  totalNotificationCount: number = 0;
  notifications: Array<NotificationModel> = [];

  constructor(private notificationService: NotificationService, 
    private authService: AuthService, 
    private userManagementService: UserManagementService, 
    private router: Router,
    private translate: TranslateService,
  ) { }

  dateDifference(actualDate: string) {
    // Calculate time between two dates:
    const date1: any = new Date(actualDate); // the date you already commented/ posted
    const date2: any = new Date(); // today

    let message: string = "";

    const diffInSeconds: number = Math.abs(date2 - date1) / 1000;
    const days: number = Math.floor(diffInSeconds / 60 / 60 / 24);
    const hours: number = Math.floor(diffInSeconds / 60 / 60 % 24);
    const minutes: number = Math.floor(diffInSeconds / 60 % 60);
    const seconds: number = Math.floor(diffInSeconds % 60);
    const milliseconds: number =
      Math.round((diffInSeconds - Math.floor(diffInSeconds)) * 1000);

    const months: number = Math.floor(days / 31);
    const years: number = Math.floor(months / 12);    

    const keys = ['DAY', 'HOUR', 'MINUTE', 'MONTH', 'YEAR'];
    const translations: { [key: string]: string } = {};

    keys.forEach(key => {
      this.translate.get(key).subscribe(translation => {
        translations[key] = translation;
      });
    });

    const dayText = translations['DAY'];
    const hourText = translations['HOUR'];
    const minuteText = translations['MINUTE'];
    const monthText = translations['MONTH'];
    const yearText = translations['YEAR'];

    // check if difference is in years or months
    if (years === 0 && months === 0) {
      // show in days if no years / months
      if (days > 0) {
        if (days === 1) {
          message = days + ' ' + dayText;
        } else { message = days + ' ' + dayText; }
      } else if (hours > 0) {
        // show in hours if no years / months / days
        if (hours === 1) {
          message = hours + ' ' + hourText;
        } else {
          message = hours + ' ' + hourText;
        }
      } else {
        // show in minutes if no years / months / days / hours
        if (minutes === 1) {
          message = minutes + ' ' + minuteText;
        } else { message = minutes + ' ' + minuteText; }
      }
    } else if (years === 0 && months > 0) {
      // show in months if no years
      if (months === 1) {
        message = months + ' ' + monthText;
      } else { message = months + ' ' + monthText; }
    } else if (years > 0) {
      // show in years if years exist
      if (years === 1) {
        message = years + ' ' + yearText;
      } else { message = years + ' ' + yearText; }
    }

    return message;
  }

  getNotifications() {
    this.notificationService.notifications$.subscribe(result => {
      this.unreadedNotificationCount = 0;
      this.totalNotificationCount = 0;
      this.notifications = [];

      if (result) {

        result.forEach(item => {
          if (item.isReaded) {
            item.state = 'primary';
          }
          else {
            item.state = 'warning';
            this.unreadedNotificationCount++;
          }

          item.time = this.dateDifference(item.date);
        });

        this.totalNotificationCount = result.length;
        this.notifications = result;

      }
    })
  }

  ngOnInit(): void {
    this.unreadedNotificationCount = 0;
    this.totalNotificationCount = 0;
    this.notifications = [];
    
    if(this.authService.currentUserValue) {
      this.notificationService.updateNotifications(this.authService.currentUserValue?.id!);
    }

    this.getNotifications();
    this.authService.currentUserSubject.asObservable().subscribe(result => {
      if (result) {
        this.isCurrentUserExist = true;
        if (result?.roles) {
          let roleList = (JSON.parse(result?.roles) as number[]);

          if (roleList.length > 0) {
            if (roleList.includes(1) || roleList.includes(2) || roleList.includes(3)) {
              this.isAdmin = true;

              if(roleList.includes(1)) {
                this.hasShoppingPermission = false;
              }
              else{
                this.hasShoppingPermission = true;
              }
            }
            else {
              this.isAdmin = false;
              this.hasShoppingPermission = true;
            }
          }
          else {
            this.isAdmin = false;
          }
        }

        this.userManagementService.updateUser(result?.id!);

        this.userManagementService.user$.subscribe(result => {
          this.user = result!;
        });
      }
      else {
        this.isCurrentUserExist = false;
        this.isAdmin = false;
        this.hasShoppingPermission = true;
      }
    });
  }

  routeToAdminPanel() {
    this.router.navigate(['/dashboard']);
  }

  routeToLogin() {
    this.router.navigate(['/auth/login']);
  }

  routeToShopping() {
    this.router.navigate(['/shopping']);
  }
}


