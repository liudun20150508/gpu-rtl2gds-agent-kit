// =============================================================
// 4 位扫描链 + testbench（用于生成示例波形）
//
// 这不是完整的 DFT 插入流程（那见 flow/dft/02_scan_insert.py），
// 而是一个最小的、可复现的扫描移位时序示例：
//   scan_en=0 → 并行装载功能数据
//   scan_en=1 → scan_in 串入，链尾从 scan_out 串出
//
// 跑法（需要 iverilog）：
//   cd examples/waveforms
//   iverilog -o /tmp/scan_chain.vvp scan_chain_tb.v && vvp /tmp/scan_chain.vvp
//   python3 ../../flow/plot_waveform.py scan_shift.vcd -o scan_shift.svg \
//       --title "扫描链移位与捕获时序" \
//       --signals clk,scan_en,scan_in,scan_out,d,q
//   （--signals 用来滤掉 vvp 内部的 W[31:0] 之类无关信号；
//     同名信号由脚本自动去重，tb 与 DUT 共享的线只画一次）
// =============================================================
`timescale 1ns/1ps

module scan_chain #(
    parameter W = 4
) (
    input  wire         clk,
    input  wire         scan_en,   // 1=移位(shift)  0=捕获/功能(capture)
    input  wire         scan_in,
    input  wire [W-1:0] d,
    output wire         scan_out
);
    reg [W-1:0] q;

    always @(posedge clk) begin
        if (scan_en)
            q <= {q[W-2:0], scan_in};   // 移位：链尾先出
        else
            q <= d;                     // 捕获功能数据
    end

    assign scan_out = q[W-1];
endmodule


module scan_chain_tb;
    reg         clk = 1'b0;
    reg         scan_en = 1'b0;
    reg         scan_in = 1'b0;
    reg  [3:0]  d = 4'h0;
    wire        scan_out;

    scan_chain u_dut (
        .clk(clk), .scan_en(scan_en), .scan_in(scan_in), .d(d), .scan_out(scan_out)
    );

    always #5 clk = ~clk;   // 10 ns 周期 = 100 MHz

    initial begin
        $dumpfile("scan_shift.vcd");
        $dumpvars(0, scan_chain_tb);

        // ① 捕获：并行装载 4'b1010
        d = 4'b1010; scan_en = 1'b0; #10;

        // ② 移位：串入 1100，链尾 1010 依次移出
        scan_en = 1'b1;
        scan_in = 1'b1; #10;
        scan_in = 1'b1; #10;
        scan_in = 1'b0; #10;
        scan_in = 1'b0; #10;

        // ③ 继续移位，把整条链（1100）送出
        scan_in = 1'b0; #40;

        // ④ 回到捕获模式
        scan_en = 1'b0; #10;
        $finish;
    end
endmodule
