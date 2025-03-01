from math import floor
import machine

GPIO_PORT=4

# Usage of ULP on ESP32S3 requires commits:
# - Enable ULP for ESP32S3
#   - https://github.com/insighio/micropython/commit/74a63155ed43296e40b35e97a5125a28a077eb2d
# - Support auxilary function ULP.init_gpio
#   - https://github.com/insighio/micropython/commit/33b18e0b67f73f27affff86acc796539a14f8b07


sourceESPIDF = """\

#define DR_REG_RTCIO_BASE            0x60008400
#define DR_REG_SENS_BASE             0x60008800

#define RTC_GPIO_IN_REG              (DR_REG_RTCIO_BASE + 0x24)
#define RTC_GPIO_IN_NEXT_S           10

#define SENS_IOMUX_CLK_EN                   (BIT(31))
#define SENS_SAR_PERI_CLK_GATE_CONF_REG     (DR_REG_SENS_BASE + 0x104)

  /* Define variables, which go into .bss section (zero-initialized data) */

next_edge: .long 0
edge_count: .long 0
debounce_counter: .long 3
debounce_max_count: .long 3
io_number: .long {}

	/* Code goes into .text section */
	.text
	.global entry
entry:
	/* Load io_number */
	move r3, io_number
	ld r3, r3, 0

	/* Read the value of lower 16 RTC IOs into R0 */
	READ_RTC_REG(RTC_GPIO_IN_REG, RTC_GPIO_IN_NEXT_S, 16)
	rsh r0, r0, r3
	jump read_done

read_done:
	and r0, r0, 1
	/* State of input changed? */
	move r3, next_edge
	ld r3, r3, 0
	add r3, r0, r3
	and r3, r3, 1
	jump edge_detected, eq
	/* Not changed */
	/* Reset debounce_counter to debounce_max_count */
	move r3, debounce_max_count
	move r2, debounce_counter
	ld r3, r3, 0
	st r3, r2, 0
	/* End program */
	halt

	.global changed
changed:
	/* Input state changed */
	/* Has debounce_counter reached zero? */
	move r3, debounce_counter
	ld r2, r3, 0
	add r2, r2, 0 /* dummy ADD to use "jump if ALU result is zero" */
	jump edge_detected, eq
	/* Not yet. Decrement debounce_counter */
	sub r2, r2, 1
	st r2, r3, 0
	/* End program */
	halt

	.global edge_detected
edge_detected:
	/* Reset debounce_counter to debounce_max_count */
	move r3, debounce_max_count
	move r2, debounce_counter
	ld r3, r3, 0
	st r3, r2, 0
	/* Flip next_edge */
	move r3, next_edge
	ld r2, r3, 0
	add r2, r2, 1
	and r2, r2, 1
	st r2, r3, 0
	/* Increment edge_count */
	move r3, edge_count
	ld r2, r3, 0
	add r2, r2, 1
	st r2, r3, 0
	halt

""".format(GPIO_PORT)

load_addr, entry_addr = 0, 5*4
ULP_MEM_BASE = 0x50000000
ULP_DATA_MASK = 0xffff  # ULP data is only in lower 16 bits

def init_ulp():
    from esp32 import ULP
    from external.esp32_ulp import src_to_binary

    binary = src_to_binary(sourceESPIDF, cpu="esp32s3")
    ulp = ULP()

    ulp.load_binary(load_addr, binary)

    init_gpio(GPIO_PORT, ulp)
    ulp.set_wakeup_period(0, 20000)  # use timer0, wakeup after 20.000 cycles

    ulp.run(entry_addr)
    print("ULP Started")

def init_gpio(gpio_num, ulp=None):
    if ulp is None:
        from esp32 import ULP
        ulp = ULP()
    try:
        ulp.init_gpio(gpio_num)
    except:
        print("ULP.init_gpio not supported")

def value(start=0):
    """
    Function to read variable from ULP memory
    """
    val = (int(hex(machine.mem32[ULP_MEM_BASE + start*4] & ULP_DATA_MASK),16))
    print("Reading value[{}]: {}".format(start, val))
    return val

def setval(start=0, value=0x0):
    """
    Function to set variable in ULP memory
    """
    machine.mem32[ULP_MEM_BASE + start*4] = value

def read_ulp_values():
    print("pulses: {}".format(floor(value(1)//2)))
    setval(1, 0x0)


def start():
    if machine.reset_cause()==machine.PWRON_RESET or machine.reset_cause()==machine.HARD_RESET or machine.reset_cause()==machine.SOFT_RESET:
        init_ulp()
    else:
        init_gpio(GPIO_PORT)
    read_ulp_values()
    print("about to sleep for 1 minute")
    machine.deepsleep(60000)
