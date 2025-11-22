# Changelog

## [0.3.0](https://github.com/vshulcz/ozon_price_tracker/compare/v0.2.0...v0.3.0) (2025-11-22)


### Features

* **cd:** cd workflow fixed ([cefaf97](https://github.com/vshulcz/ozon_price_tracker/commit/cefaf97f21d7e2cc4d6a7c3efeaea52cbf6ebb77))
* logging upgraded ([6338479](https://github.com/vshulcz/ozon_price_tracker/commit/63384799d4314cef21474bbe5cf38de8c15a33a9))
* logging upgraded ([fd50869](https://github.com/vshulcz/ozon_price_tracker/commit/fd50869e82089e5b9728f8316930b1692abf25d2))


### Documentation

* deployment guide ([29789d2](https://github.com/vshulcz/ozon_price_tracker/commit/29789d2592d9397dd1736c19a5577c0cfa59afe3))

## [0.2.0](https://github.com/vshulcz/ozon_price_tracker/compare/v0.1.1...v0.2.0) (2025-11-22)


### Features

* argocd, k8s, cd workflow added ([2df2d25](https://github.com/vshulcz/ozon_price_tracker/commit/2df2d2597dd10199ef73c42d22e342541b43f398))
* argocd, k8s, cd workflow added ([eab61f6](https://github.com/vshulcz/ozon_price_tracker/commit/eab61f6313a80961ed6ba6857fa7923a68406d8f))
* **cd:** cd workflow modified ([1275a83](https://github.com/vshulcz/ozon_price_tracker/commit/1275a8387d9b49e29361ab800613912f23f35924))


### Bug Fixes

* **ci:** publish Docker image with 'latest' tag for main branch ([ffd7ebb](https://github.com/vshulcz/ozon_price_tracker/commit/ffd7ebbd88d5f3df740de37b9d65b9923520d317))
* **k8s:** change postgres PGDATA to /pgdata to avoid mount conflicts ([e648528](https://github.com/vshulcz/ozon_price_tracker/commit/e648528b075e6b286abd5eefe4f469c7ebd91386))
* **k8s:** properly replace PVC with emptyDir for dev PostgreSQL using JSON patch ([c9dd13d](https://github.com/vshulcz/ozon_price_tracker/commit/c9dd13d3573ef47c2694f06793c97ed0df143ffb))
* **k8s:** remove secret from ArgoCD management - secrets created manually ([efd5808](https://github.com/vshulcz/ozon_price_tracker/commit/efd5808e408bff06cfd956dac590c3d250de0abb))
* **k8s:** remove subPath from postgres volumeMount to fix mount errors ([c413dbc](https://github.com/vshulcz/ozon_price_tracker/commit/c413dbc1637e8a331e145422aaf5840e9bc1030c))
* **k8s:** use emptyDir for PostgreSQL in dev environment ([cabb476](https://github.com/vshulcz/ozon_price_tracker/commit/cabb476bebb3655ec8f08c84ce128bcc8f4d1134))


### Documentation

* readme updated ([d7bc852](https://github.com/vshulcz/ozon_price_tracker/commit/d7bc85266d1f750b8325f959b021189332217bbe))
* readme updated ([85a4afa](https://github.com/vshulcz/ozon_price_tracker/commit/85a4afaf063e16d6ef16798d4cf8aeee3b20d4ac))

## [0.1.1](https://github.com/vshulcz/ozon_price_tracker/compare/v0.1.0...v0.1.1) (2025-11-04)


### Bug Fixes

* coverage increased ([d0ba6ad](https://github.com/vshulcz/ozon_price_tracker/commit/d0ba6ade606d42eea654e5b5f72085c0f79b09fa))
* pg session ([5d71d3d](https://github.com/vshulcz/ozon_price_tracker/commit/5d71d3d8ddbf09e4333487c1ebcc81d3660d688a))
* pg session ([4e9c228](https://github.com/vshulcz/ozon_price_tracker/commit/4e9c2288e318f02dd97766001b72aa719d009adb))

## 0.1.0 (2025-11-04)


### Features

* ci, tests added ([aa2df40](https://github.com/vshulcz/ozon_price_tracker/commit/aa2df40c3458e0d9db9de75612c18a9a68bcf9c5))
* ci, tests added ([633954f](https://github.com/vshulcz/ozon_price_tracker/commit/633954fb57f9a3f0add7461d1d9e08d5dfeddd6c))


### Bug Fixes

* release-please ([534d443](https://github.com/vshulcz/ozon_price_tracker/commit/534d443f70009147ac14115735b168c28350d792))
