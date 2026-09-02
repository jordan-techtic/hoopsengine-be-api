# Hoops Engine API Testing Checklist

**Total APIs:** 207 operations across 161 paths  
**Base URL:** `/api/v1`  
**OpenAPI:** `/openapi.json` or `/docs`  
**Auth:** `Authorization: Bearer <JWT>` (except public endpoints)

**Recommended testing order:** Super Admin → Organization Admin → Coach → Player → Stripe Webhook

---

## How to use this document

- Test APIs in the sequence listed below (dependencies flow top to bottom).
- Mark each item as Pass / Fail / Blocked during QA/UAT.
- Use the JWT from the role's login endpoint before testing authenticated routes.
- Stripe subscription flows require Super Admin plans to exist before Org Admin/Coach upgrade tests.

---

## PHASE 0 — System / Infrastructure (2 APIs)

1. **GET** `/` — Root / API info (Public)
2. **GET** `/api/v1/health` — Health check (Public)

---

## PHASE 1 — SUPER ADMIN (26 APIs)

Aligns with proposal **Section 5: Admin** — Login, Dashboard, Organizations, Users, Subscriptions, Profile, Support.

### 1A. Authentication

3. **POST** `/api/v1/auth/login` — Super Admin login; returns JWT (Public)
4. **POST** `/api/v1/auth/forgot-password` — Request password reset email (Public)
5. **POST** `/api/v1/auth/validate-reset-token` — Validate reset token (Public)
6. **POST** `/api/v1/auth/reset-password` — Reset password with token (Public)

### 1B. Dashboard

7. **GET** `/api/v1/super-admin/dashboard` — Dashboard analytics: organizations, coaches, players, sessions, subscriptions, revenue

### 1C. Organization Management

8. **GET** `/api/v1/super-admin/organizations` — List all organizations
9. **POST** `/api/v1/super-admin/organizations` — Create a new organization
10. **PUT** `/api/v1/super-admin/organizations/{organization_id}` — Edit an organization
11. **DELETE** `/api/v1/super-admin/organizations/{organization_id}` — Remove an organization

### 1D. User Management

12. **GET** `/api/v1/super-admin/users` — List all users across organizations
13. **POST** `/api/v1/super-admin/users` — Add a new user
14. **PUT** `/api/v1/super-admin/users/{user_id}` — Edit an existing user
15. **DELETE** `/api/v1/super-admin/users/{user_id}` — Remove a user

### 1E. Stripe Subscription Plans

16. **GET** `/api/v1/super-admin/subscription-plans/currencies` — List Stripe-supported currencies
17. **GET** `/api/v1/super-admin/subscription-plans` — List subscription plans (filter by role, status)
18. **POST** `/api/v1/super-admin/subscription-plans` — Create subscription plan (syncs to Stripe)
19. **GET** `/api/v1/super-admin/subscription-plans/{plan_id}` — Get subscription plan details
20. **PUT** `/api/v1/super-admin/subscription-plans/{plan_id}` — Update subscription plan
21. **DELETE** `/api/v1/super-admin/subscription-plans/{plan_id}` — Archive subscription plan

### 1F. Profile

22. **GET** `/api/v1/super-admin/profile` — Get super admin profile
23. **PUT** `/api/v1/super-admin/profile` — Update super admin profile
24. **GET** `/api/v1/super-admin/profile/avatar` — Get super admin profile avatar

### 1G. Support Requests

25. **GET** `/api/v1/support-requests` — List support requests
26. **POST** `/api/v1/support-requests` — Create a support request
27. **GET** `/api/v1/support-requests/{request_id}/attachment` — Download support request attachment

### 1H. Logout

28. **POST** `/api/v1/auth/logout` — Logout / invalidate session

---

## PHASE 2 — ORGANIZATION ADMIN (72 APIs)

Aligns with proposal **Section 4: Organisation/Academy** — Auth, Teams, Coaches, Players, Practice Plans, Analytics, Subscription, Settings, Help.

### 2A. Authentication

29. **POST** `/api/v1/organization/login` — Organization admin login; returns JWT
30. **POST** `/api/v1/admin/reset-password` — Reset organization admin password
31. **GET** `/api/v1/admin/reset-password/validate` — Validate new password strength
32. **POST** `/api/v1/admin/change-password` — Change password (admin path)
33. **POST** `/api/v1/organization/change-password` — Change password (organization path)

### 2B. Profile

34. **GET** `/api/v1/organization/profile` — Get organization profile
35. **PUT** `/api/v1/organization/profile` — Update organization profile (name, address, logo, etc.)

### 2C. Team Management

36. **POST** `/api/v1/admin/teams` — Create an organization team (admin path)
37. **GET** `/api/v1/admin/teams/{team_id}` — Retrieve team details for editing
38. **PUT** `/api/v1/admin/teams/{team_id}` — Update team details
39. **DELETE** `/api/v1/admin/teams/{team_id}` — Delete an organization team
40. **GET** `/api/v1/teams` — List organization teams
41. **POST** `/api/v1/teams` — Create a team (canonical path)
42. **GET** `/api/v1/teams/search` — Search teams by name
43. **GET** `/api/v1/teams/{team_id}` — Retrieve team details
44. **PUT** `/api/v1/teams/{team_id}` — Update team details
45. **DELETE** `/api/v1/teams/{team_id}` — Delete a team

### 2D. Coach Management

46. **POST** `/api/v1/admin/invite-coach` — Invite a coach by email
47. **GET** `/api/v1/admin/search-coaches` — Search organization coaches
48. **GET** `/api/v1/admin/coaches/{coach_id}` — Retrieve coach details
49. **PUT** `/api/v1/admin/coaches/{coach_id}` — Update coach details
50. **DELETE** `/api/v1/admin/coaches/{coach_id}` — Remove a coach from the organization

### 2E. Player Management

51. **GET** `/api/v1/admin/players/{player_id}` — Retrieve player details for editing
52. **PUT** `/api/v1/admin/players/{player_id}` — Update player details
53. **GET** `/api/v1/admin/players/{player_id}/removal` — Get player details for removal confirmation
54. **DELETE** `/api/v1/admin/players/{player_id}` — Remove player from organization

### 2F. Practice Plans

55. **GET** `/api/v1/admin/practice-plans` — List organization practice plans
56. **POST** `/api/v1/admin/practice-plans` — Create an organization practice plan
57. **PUT** `/api/v1/admin/practice-plans/{plan_id}` — Update an organization practice plan
58. **DELETE** `/api/v1/admin/practice-plans/{plan_id}` — Delete an organization practice plan
59. **GET** `/api/v1/practice-plans` — List active practice plans
60. **POST** `/api/v1/practice-plans` — Create a practice plan
61. **POST** `/api/v1/practice-plans/assign` — Assign a practice plan to a coach or team
62. **GET** `/api/v1/practice-plans/search` — Search team roster
63. **PUT** `/api/v1/practice-plans/{plan_id}` — Update a practice plan or assignment
64. **DELETE** `/api/v1/practice-plans/{plan_id}` — Delete a practice plan or assignment

### 2G. Analytics and Reports

65. **GET** `/api/v1/analytics` — Get analytics dashboard
66. **POST** `/api/v1/analytics/filter` — Apply analytics filters
67. **POST** `/api/v1/analytics/export` — Export analytics insights
68. **POST** `/api/v1/reports/generate` — Generate organization report
69. **GET** `/api/v1/reports/{report_id}` — Get generated report details
70. **POST** `/api/v1/reports/export` — Export generated report

### 2H. Stripe Billing and Subscription

71. **GET** `/api/v1/admin/subscription` — Get organization subscription details
72. **POST** `/api/v1/admin/subscription/upgrade` — Upgrade organization subscription plan (Stripe checkout)
73. **GET** `/api/v1/admin/billing/history` — Get organization billing history
74. **POST** `/api/v1/admin/billing/payment-method` — Update organization payment method
75. **GET** `/api/v1/billing/history` — Get billing history (alias path)
76. **PUT** `/api/v1/billing/payment-method` — Update payment method (alias path)
77. **GET** `/api/v1/subscription` — Get current subscription details
78. **POST** `/api/v1/subscription/upgrade` — Upgrade subscription plan
79. **POST** `/api/v1/subscription/cancel` — Cancel subscription

### 2I. Custom UI

80. **GET** `/api/v1/custom-ui/designs` — List custom UI design templates
81. **POST** `/api/v1/custom-ui/design` — Save custom UI design template
82. **GET** `/api/v1/ui-design/templates` — List UI design templates (alias path)
83. **POST** `/api/v1/ui-design/save` — Save customized UI design template (alias path)
84. **POST** `/api/v1/ui-design/feedback` — Submit UI design feedback

### 2J. Settings, Help, and Leaderboard

85. **PUT** `/api/v1/account/settings/profile` — Update account profile details
86. **PUT** `/api/v1/account/settings/organization` — Update organization information
87. **POST** `/api/v1/account/settings/change-password` — Change authenticated user password
88. **PATCH** `/api/v1/account/settings/push-notifications` — Enable or disable push notifications
89. **PUT** `/api/v1/account/settings/authentication-keys` — Update authentication keys
90. **GET** `/api/v1/account/settings/help-support` — Retrieve help and support information
91. **POST** `/api/v1/account/settings/help-support/contact` — Submit support request from Account Settings
92. **GET** `/api/v1/faqs` — Retrieve FAQs
93. **GET** `/api/v1/faqs/{faq_id}` — Retrieve a single FAQ by ID
94. **POST** `/api/v1/faqs/contact-support` — Contact support from FAQs
95. **GET** `/api/v1/support/contact/info` — Get support contact information
96. **POST** `/api/v1/support/contact` — Submit a support message
97. **GET** `/api/v1/leaderboard` — Get leaderboard rankings
98. **GET** `/api/v1/leaderboard/filter` — Filter leaderboard by performance metric
99. **GET** `/api/v1/leaderboard/search` — Search leaderboard players by name (GET)
100. **POST** `/api/v1/leaderboard/search` — Search leaderboard players by name (POST)

---

## PHASE 3 — COACH (72 APIs)

Aligns with proposal **Section 2: Coach Frontend** — Auth, Home, Record Session, Practice Plans, Players, Statistics, Offline Sync, Help.

### 3A. Registration and Authentication

101. **POST** `/api/v1/register` — Register a new coach
102. **POST** `/api/v1/verify-email` — Verify email with OTP code
103. **POST** `/api/v1/resend-verification-code` — Resend email verification code
104. **GET** `/api/v1/coach/continue-verification` — Continue pending email verification
105. **POST** `/api/v1/coach/cancel-verification` — Cancel pending email verification
106. **POST** `/api/v1/coach/login` — Coach login; returns JWT
107. **POST** `/api/v1/coach/forgot-password` — Coach forgot password
108. **POST** `/api/v1/reset-password` — Reset authenticated user password
109. **GET** `/api/v1/reset-password/validate` — Validate new password strength

### 3B. Role Selection

110. **GET** `/api/v1/role-selection/roles` — List selectable roles
111. **GET** `/api/v1/role-selection` — Get current role selection
112. **POST** `/api/v1/role-selection` — Submit selected role

### 3C. Home Dashboard

113. **GET** `/api/v1/coach/home` — Get coach home screen data (org name, team, sessions, players)
114. **GET** `/api/v1/home/user-info` — Get home user info
115. **GET** `/api/v1/home/activities` — Get home activities
116. **GET** `/api/v1/home/notifications` — Get home notifications

### 3D. Profile

117. **GET** `/api/v1/profile` — Get current coach profile
118. **PUT** `/api/v1/profile` — Update current coach profile

### 3E. One Drill Flow — Step 1: Select Player

119. **POST** `/api/v1/coach/drills/search` — Search players for One Drill Step 1
120. **POST** `/api/v1/coach/drills/select_player` — Select a player for One Drill Step 1
121. **POST** `/api/v1/coach/drills/continue` — Continue from Step 1 to Step 2 (drill selection)

### 3F. One Drill Flow — Step 2: Select Drill

122. **GET** `/api/v1/drills` — List drills for One Drill Step 2
123. **GET** `/api/v1/drills/search` — Search drills by name (practice plan picker)
124. **GET** `/api/v1/drills/{drill_id}` — Get drill details
125. **POST** `/api/v1/drills/continue` — Continue One Drill flow after drill selection

### 3G. One Drill Flow — Step 3: Record Session

126. **GET** `/api/v1/sessions/modes` — List available session recording modes
127. **GET** `/api/v1/sessions/modes/{mode}` — Get a session mode by identifier
128. **POST** `/api/v1/sessions` — Create a One Drill Step 3 session
129. **POST** `/api/v1/sessions/record` — Record a session for a selected drill or mode
130. **PUT** `/api/v1/sessions/record/{session_id}` — Update an existing session record
131. **GET** `/api/v1/sessions/summary` — List One Drill session summaries
132. **GET** `/api/v1/sessions/{session_id}` — Get One Drill session details
133. **PUT** `/api/v1/sessions/{session_id}` — Update One Drill session metrics
134. **POST** `/api/v1/sessions/{session_id}/next-drill` — Navigate to the next drill in the session
135. **POST** `/api/v1/sessions/{session_id}/end-practice` — End the current practice session

### 3H. Attendance (Daily Options)

136. **GET** `/api/v1/attendance/players/search` — Search attendance players
137. **GET** `/api/v1/attendance/summary` — Get attendance summary
138. **POST** `/api/v1/attendance/start-practice` — Start practice from attendance

### 3I. Live Practice

139. **GET** `/api/v1/live_practice/drills` — List live practice drills
140. **POST** `/api/v1/live_practice/drills` — Create live practice drill
141. **PUT** `/api/v1/live_practice/drills/{drill_id}` — Update live practice drill
142. **DELETE** `/api/v1/live_practice/drills/{drill_id}` — Delete live practice drill
143. **POST** `/api/v1/live_practice/timer/start` — Start live practice timer
144. **GET** `/api/v1/live_practice/timer/status` — Get live practice timer status
145. **POST** `/api/v1/live_practice/timer/stop` — Stop live practice timer
146. **POST** `/api/v1/live_practice/players/{player_id}/shots` — Record player shots
147. **GET** `/api/v1/live_practice/players/{player_id}/statistics` — Get player live practice statistics

### 3J. Practice Plans

148. **GET** `/api/v1/coach/practice-plans/{plan_id}` — Get a practice plan by ID
149. **POST** `/api/v1/coach/practice-plans` — Create a practice plan
150. **PUT** `/api/v1/coach/practice-plans/{plan_id}` — Update a practice plan
151. **DELETE** `/api/v1/coach/practice-plans/{plan_id}` — Delete a practice plan

### 3K. Player Management

152. **GET** `/api/v1/players` — List organization players
153. **GET** `/api/v1/players/search` — Search coach players
154. **POST** `/api/v1/players` — Add a new player
155. **GET** `/api/v1/players/{player_id}` — Get player details
156. **PUT** `/api/v1/players/{player_id}` — Update player details
157. **GET** `/api/v1/coach/confirm_removal` — Get player removal confirmation copy
158. **POST** `/api/v1/coach/remove_player` — Remove player by email and phone
159. **DELETE** `/api/v1/players/{player_id}` — Remove player from roster

### 3L. Drill Catalog

160. **POST** `/api/v1/drills` — Create a catalog drill
161. **PUT** `/api/v1/drills/{drill_id}` — Update a catalog drill
162. **DELETE** `/api/v1/drills/{drill_id}` — Delete a catalog drill

### 3M. Statistics

163. **GET** `/api/v1/statistics/{player_id}` — Get player statistics

### 3N. Offline Sync

164. **GET** `/api/v1/coach/sync/preferences` — Get coach sync preferences
165. **PUT** `/api/v1/coach/sync/preferences` — Update coach sync preferences
166. **POST** `/api/v1/coach/sync` — Trigger coach data sync
167. **GET** `/api/v1/coach/sync-activity` — Get coach sync activity
168. **POST** `/api/v1/coach/sync-activity/save` — Save coach sync activity updates
169. **GET** `/api/v1/coach/queue` — List coach queue items pending sync
170. **POST** `/api/v1/coach/queue` — Update a coach queue item sync status
171. **POST** `/api/v1/coach/clear-cache` — Clear coach local cache metadata

### 3O. Help and Drill Ideas

172. **POST** `/api/v1/drill-ideas` — Submit a custom drill idea
173. **GET** `/api/v1/drill-ideas` — List submitted drill ideas

---

## PHASE 4 — PLAYER (33 APIs)

Aligns with proposal **Section 3: Player Side** — Invitation, Auth, Home, Workout, Progress, Help, Settings.

### 4A. Invitation and Authentication

174. **POST** `/api/v1/player/verify-code` — Verify player invitation or recovery code
175. **GET** `/api/v1/player/cancel-verification` — Get cancel verification instructions
176. **POST** `/api/v1/player/cancel-verification` — Cancel pending player email verification
177. **GET** `/api/v1/login/validate` — Validate player login fields
178. **POST** `/api/v1/login` — Player login; returns JWT
179. **POST** `/api/v1/player/forgot-password` — Player forgot password
180. **POST** `/api/v1/player/reset-password-with-token` — Reset player password with recovery token
181. **POST** `/api/v1/player/reset-password` — Reset authenticated player password
182. **POST** `/api/v1/player/change-password` — Change authenticated player password

### 4B. Role Selection

183. **GET** `/api/v1/player/role-selection` — Get current role selection (player path)
184. **POST** `/api/v1/player/role-selection` — Submit selected role (player path)

### 4C. Home and Profile

185. **GET** `/api/v1/player/home` — Get authenticated player home screen data
186. **GET** `/api/v1/player/profile` — Get current player profile
187. **PUT** `/api/v1/player/profile` — Update current player profile

### 4D. Workout and Training

188. **GET** `/api/v1/player/start` — Get workout statistics and today's drill list
189. **POST** `/api/v1/player/start` — Start a player workout session
190. **GET** `/api/v1/player/drills` — List active drills for the authenticated player
191. **GET** `/api/v1/player/drills/{drill_id}` — Get details for a specific player drill
192. **POST** `/api/v1/player/drills/start` — Start the timer for the current player drill
193. **POST** `/api/v1/player/drills/{drill_id}/play` — Start drill playback for Active Drill
194. **PUT** `/api/v1/player/drills/{drill_id}/timer` — Update the timer for an active player drill
195. **POST** `/api/v1/player/drills/{drill_id}/stop` — Stop the timer for a specific player drill
196. **POST** `/api/v1/player/drills/reset` — Reset the timer for the current player drill
197. **POST** `/api/v1/drills/{drill_id}/play` — Start drill playback (HE-213 ticket path alias)
198. **PUT** `/api/v1/drills/{drill_id}/timer` — Update active drill timer (HE-213 ticket path alias)

### 4E. Progress

199. **GET** `/api/v1/player/my-progress` — Get authenticated player progress summary
200. **GET** `/api/v1/player/session-history` — Get authenticated player session history
201. **GET** `/api/v1/player/drill-performance` — Get authenticated player drill performance

### 4F. Help and Support

202. **POST** `/api/v1/player/drill-submissions` — Submit a player drill idea
203. **GET** `/api/v1/player/drill-submissions` — List player drill submissions
204. **GET** `/api/v1/player/drill-submissions/{submission_id}` — Get player drill submission by ID
205. **GET** `/api/v1/support/contact` — Get player support contact information
206. **POST** `/api/v1/support/inquiries` — Submit a player support inquiry

---

## PHASE 5 — STRIPE WEBHOOK (1 API)

207. **POST** `/api/v1/webhooks/stripe` — Stripe webhook handler for subscription sync (requires Stripe-Signature header)

---

## Stripe Subscription Testing Flow

Test in this order when validating Stripe integration:

1. Super Admin creates subscription plans (APIs #16–21) — plans sync to Stripe Products/Prices
2. Organization Admin or Coach calls upgrade endpoint (API #72 or #78) — returns Stripe Checkout URL
3. Complete payment on Stripe Checkout
4. Stripe sends webhook to API #207 — subscription status updated in database
5. Verify subscription with `GET /api/v1/subscription` (API #77) or `GET /api/v1/admin/subscription` (API #71)
6. Test cancel flow with `POST /api/v1/subscription/cancel` (API #79)

See also: `docs/admin-stripe-subscription-api.md`

---

## Prerequisites Before Testing Each Role

**Organization Admin**
- Super Admin must create an organization first (API #9)
- Org admin user must exist and be linked to that organization

**Coach**
- Organization Admin must invite the coach (API #46)
- Coach completes registration and email verification (APIs #101–102)

**Player**
- Coach or Org Admin must add/invite the player (API #154 or org admin player APIs #51–54)
- Player receives invitation code for verification (API #174)

**Sessions, Leaderboard, Statistics**
- Coach must record at least one session (APIs #128–135) before player progress/leaderboard data exists

**Stripe Subscription**
- Super Admin must create subscription plans (API #18)
- Stripe API keys and webhook secret must be configured in `.env`
- Webhook endpoint must be registered in Stripe Dashboard: `https://YOUR_API_DOMAIN/api/v1/webhooks/stripe`

---

## Shared / Multi-Role APIs

These endpoints are used by more than one role. Test each with the appropriate role JWT:

- **Leaderboard** — APIs #97–100 (Org Admin, Coach, Player)
- **Subscription** — APIs #77–79 (Org Admin, Coach)
- **Account Settings** — APIs #85–91 (Org Admin, Coach)
- **FAQs and Support** — APIs #92–96, #205–206 (all roles)
- **Statistics** — API #163 (Coach views player stats; requires recorded sessions)

---

## Role Login Reference

- **Super Admin:** `POST /api/v1/auth/login`
- **Organization Admin:** `POST /api/v1/organization/login`
- **Coach:** `POST /api/v1/coach/login`
- **Player:** `POST /api/v1/login`

---

*Generated from codebase OpenAPI schema. Last updated: September 2026.*
