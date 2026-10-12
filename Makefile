# rtl2gds-agent-kit — 统一入口
#
# make install                    # 自动探测已安装的 agent 并部署知识库
# make install AGENT=claude-code  # 只部署到指定 agent
# make doctor                     # 检查环境与部署状态
# make demo                       # 用示例报告跑一次规则引擎
# make test                       # 跑引擎单元测试

SHELL := /bin/bash
PY    ?= python3
AGENT ?=
SCOPE ?= project

.PHONY: help install uninstall doctor deps deps-install fixes fixes-list demo test clean

help:
	@echo "rtl2gds-agent-kit"
	@echo ""
	@echo "  make install [AGENT=<name>] [SCOPE=project|global]  部署知识库到 agent"
	@echo "  make uninstall [SCOPE=...]                          卸载"
	@echo "  make doctor                                         环境自检"
	@echo "  make deps                                           检查 EDA 工具链依赖"
	@echo "  make deps-install                                   安装缺失的依赖"
	@echo "  make fixes                                          列出流程修复（含环境自检）"
	@echo "  make fixes-list                                     只列出修复清单"
	@echo "  make demo                                           规则引擎示例"
	@echo "  make test                                           引擎单元测试"
	@echo ""
	@echo "  AGENT ∈ {auto, claude-code, reasonix, codex, openclaw, all}"
	@echo "  未指定 AGENT 时等价于 auto（自动探测）。"

install:
	./install.sh $(if $(AGENT),--agent $(AGENT),--agent auto) --scope $(SCOPE)

uninstall:
	./install.sh --uninstall --scope $(SCOPE)

doctor:
	./install.sh --doctor

deps:
	./install-deps.sh --check

deps-install:
	./install-deps.sh --install

fixes:
	./flow/fixes/apply_fixes.sh --check

fixes-list:
	./flow/fixes/apply_fixes.sh --list

demo:
	$(PY) -m engine analyze --stage TIMING --report examples/reports/sta_wns_fail.rpt --no-llm

test:
	$(PY) -m unittest discover -s tests -t . -v

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf run signoff
