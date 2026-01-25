# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - alert [ref=e2]
  - generic [ref=e4]:
    - banner [ref=e5]:
      - button "Open menu" [ref=e6] [cursor=pointer]:
        - img [ref=e7]
      - button "A" [ref=e8] [cursor=pointer]:
        - generic [ref=e10]: A
    - main [ref=e11]:
      - generic [ref=e13]:
        - img [ref=e14]
        - heading "Select a project to get started" [level=2] [ref=e16]
        - paragraph [ref=e17]: Choose a project from the sidebar to access files, chats, and settings.
  - region "Notifications (F8)":
    - list
```